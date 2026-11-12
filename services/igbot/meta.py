"""Instagram Graph API calls (Instagram API with Instagram Login).

DRY_RUN=1 (default) never calls Meta: messages go to data/outbox.jsonl instead.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

log = logging.getLogger("meta")
OUTBOX = Path(__file__).with_name("data") / "outbox.jsonl"
WINDOW = 24 * 3600  # Meta's standard messaging window


def dry() -> bool:
    return os.getenv("DRY_RUN", "1") != "0"


def _base() -> str:
    return f"https://{os.getenv('GRAPH_HOST', 'graph.facebook.com')}/{os.getenv('GRAPH_VERSION', 'v24.0')}"


def _post(path: str, body: dict) -> dict:
    if dry():
        OUTBOX.parent.mkdir(exist_ok=True)
        with OUTBOX.open("a") as f:
            f.write(json.dumps({"at": time.time(), "path": path, "body": body}, ensure_ascii=False) + "\n")
        return {"dry_run": True}
    req = urllib.request.Request(
        _base() + path, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {os.environ['IG_ACCESS_TOKEN']}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log.error("Graph API %s failed: %s %s", path, e.code, e.read()[:500])
        return {"error": e.code}


def send_dm(igsid: str, text: str, last_in: float) -> dict:
    if time.time() - last_in > WINDOW:
        log.warning("Not sending to %s: outside 24h window", igsid)
        return {"skipped": "outside_window"}
    return _post(f"/{os.environ.get('IG_USER_ID', 'me')}/messages", {"recipient": {"id": igsid}, "message": {"text": text}})


def private_reply(comment_id: str, text: str) -> dict:
    """One DM per comment, allowed within 7 days of the comment."""
    return _post(f"/{os.environ.get('IG_USER_ID', 'me')}/messages", {"recipient": {"comment_id": comment_id}, "message": {"text": text}})


def reply_comment(comment_id: str, text: str) -> dict:
    return _post(f"/{comment_id}/replies", {"message": text})


def username(igsid: str) -> str | None:
    """Best-effort lookup of the sender's @username (for notifications)."""
    if dry():
        return None
    url = f"{_base()}/{igsid}?fields=username"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {os.environ['IG_ACCESS_TOKEN']}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()).get("username")
    except Exception:
        return None
