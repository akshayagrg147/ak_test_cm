"""Webhook server for Instagram (messages, comments, story replies).

  GET  /webhook  -> Meta verification (hub.challenge)
  POST /webhook  -> events, signature-checked with APP_SECRET
  GET  /health   -> ok

Run:  .venv/bin/python server.py      (PORT from .env, default 8080)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

load_dotenv()

import flow  # noqa: E402  (needs env loaded)
import meta  # noqa: E402
import store  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("server")
WEBHOOK_PATHS = ("/webhook", "/ig-webhook")  # /ig-webhook when served behind viacrm.in
_lock = threading.Lock()  # process events one at a time (simple, avoids state races)


def valid_signature(body: bytes, header: str | None) -> bool:
    secret = os.getenv("APP_SECRET", "")
    if not secret or not header or not header.startswith("sha256="):
        return False
    good = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(good, header[7:])


def handle_payload(payload: dict) -> None:
    own_id = os.getenv("IG_USER_ID", "")
    if payload.get("object") != "instagram":
        return
    for entry in payload.get("entry", []):
        for ev in entry.get("messaging", []):
            _handle_messaging(ev, own_id or entry.get("id", ""))
        for ch in entry.get("changes", []):
            if ch.get("field") in ("comments", "live_comments"):
                _handle_comment(ch.get("value", {}), own_id or entry.get("id", ""))


def _handle_messaging(ev: dict, own_id: str) -> None:
    msg = ev.get("message")
    if not msg or msg.get("is_deleted"):
        return  # reactions, reads, postbacks etc. are ignored
    sender, recipient = ev.get("sender", {}).get("id"), ev.get("recipient", {}).get("id")
    if not store.first_seen("m:" + msg.get("mid", f"{sender}{ev.get('timestamp')}")):
        return
    text = (msg.get("text") or "").strip()
    if msg.get("is_echo") or sender == own_id:
        # Echo of something we sent. If it isn't a bot text, Akshay replied by hand -> pause bot.
        if text and text not in store.last_out(recipient):
            flow.on_owner_reply(recipient)
            log.info("owner replied manually to %s; bot paused for that chat", recipient)
        return
    if not text:
        log.info("non-text message from %s ignored: %s", sender, list(msg)[:5])
        return  # photos, stickers, link previews, reactions: a human can look later
    source = "story_reply" if msg.get("reply_to", {}).get("story") else "dm"
    ts = ev.get("timestamp", time.time() * 1000) / 1000
    uname = store.get(sender).get("username") or meta.username(sender)
    flow.on_dm(sender, text, ts, uname, source)


def _handle_comment(v: dict, own_id: str) -> None:
    frm = v.get("from", {})
    if not v.get("id") or frm.get("id") == own_id or v.get("parent_id"):
        return  # our own replies, or replies inside a thread
    if not store.first_seen("c:" + v["id"]):
        return
    flow.on_comment(v["id"], frm.get("id", ""), frm.get("username", ""), v.get("text", ""))


class H(BaseHTTPRequestHandler):
    def _send(self, code: int, body: str = "ok") -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(body.encode())

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/health", "/ig-webhook/health"):
            return self._send(200)
        if u.path in WEBHOOK_PATHS:
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            if q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == os.getenv("VERIFY_TOKEN"):
                log.info("webhook verification OK")
                return self._send(200, q.get("hub.challenge", ""))
            log.warning("webhook verification FAILED (token mismatch)")
            return self._send(403, "forbidden")
        self._send(404, "not found")

    def do_POST(self):
        if urlparse(self.path).path not in WEBHOOK_PATHS:
            return self._send(404, "not found")
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if not valid_signature(body, self.headers.get("X-Hub-Signature-256")):
            log.warning("bad signature, dropped")
            return self._send(403, "bad signature")
        self._send(200)  # ack fast; Meta retries slow webhooks
        try:
            payload = json.loads(body)
        except ValueError:
            return
        log.info("webhook POST ok: object=%s keys=%s", payload.get("object"), list(payload)[:3])

        def work():
            with _lock:
                try:
                    handle_payload(payload)
                except Exception:
                    log.exception("event failed")
        threading.Thread(target=work, daemon=True).start()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    log.info("listening on :%d  DRY_RUN=%s", port, meta.dry())
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
