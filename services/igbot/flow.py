"""Conversation logic. Pure functions of (state, message) -> replies; sending is done via meta.py."""
from __future__ import annotations

import logging
import re
import time

import brain
import meta
import notify
import store
import texts as T

log = logging.getLogger("flow")
REQUIRED = {"name", "whatsapp", "team_size", "demo_time"}  # current_tool may be skipped
PRIVATE_REPLY_COOLDOWN = 24 * 3600


def _valid(field: str, value) -> str | None:
    if value is None:
        return None
    v = str(value).strip()
    if not v:
        return None
    if field == "whatsapp":
        digits = re.sub(r"\D", "", v)[-10:]
        return digits if re.fullmatch(r"[6-9]\d{9}", digits) else None
    if field == "team_size":
        return v if re.search(r"\d", v) else None
    if field == "name":
        return v[:60] if not re.search(r"\d", v) else None
    return v[:120]


def _merge(conv: dict, details: brain.Details) -> list[str]:
    got = []
    for f in store.FIELDS:
        val = _valid(f, getattr(details, f))
        if val and not conv["details"].get(f):
            conv["details"][f] = val
            got.append(f)
    return got


def _next_field(conv: dict) -> str | None:
    for f in store.FIELDS:
        if not conv["details"].get(f):
            return f
    return None


def _faq(topic: str) -> str | None:
    return T.FAQ.get(topic)


def _handoff(conv: dict, text: str) -> str:
    conv["state"], conv["expected"] = "human", None
    notify.push("handoff", {"username": conv.get("username"), "message": text, "created": time.time()},
                T.NOTIFY_HANDOFF.format(username=conv.get("username") or conv["igsid"], text=text[:200]))
    return T.HANDOFF


def _complete(conv: dict, source: str) -> str:
    conv["state"], conv["expected"] = "done", None
    row = store.add_lead(conv, source)
    d = {k: (v or "-") for k, v in row.items()}
    if d["current_tool"] == "skip":
        d["current_tool"] = "-"
    notify.push("lead", row, T.NOTIFY_LEAD.format(**d))
    return T.LEAD_DONE.format(name=conv["details"]["name"].split()[0], demo_time=conv["details"]["demo_time"])


def _ask_next(conv: dict, source: str) -> str:
    f = _next_field(conv)
    conv["retries"] = 0
    if f is None:
        return _complete(conv, source)
    conv["state"], conv["expected"] = "collecting", f
    return T.ASK[f]


def decide(conv: dict, text: str, source: str = "dm") -> tuple[list[str], dict]:
    """Returns (reply_parts, debug). Mutates conv; caller saves it."""
    expected = conv.get("expected") if conv["state"] == "collecting" else None
    u, engine = brain.understand(text, expected, source)
    dbg = {"engine": engine, "intent": u.intent, "topic": u.faq_topic}
    st = conv["state"]

    if st == "opted_out":
        if u.intent == "opt_in":
            conv["state"] = "new"
            return [T.OPT_IN], dbg
        return [], dbg
    if u.intent == "opt_out":
        conv["state"], conv["expected"] = "opted_out", None
        return [T.OPT_OUT], dbg
    if st == "human":
        return [], dbg  # a person is handling this chat
    if u.intent == "human" or (u.faq_topic == "unknown" and u.intent in ("question", "interested")):
        return [_handoff(conv, text)], dbg

    got = _merge(conv, u.details)

    if st == "collecting":
        if u.intent == "pause":
            conv["state"], conv["expected"] = "paused", None
            return [T.COLLECT_PAUSED], dbg
        if u.intent == "not_interested":
            conv["state"], conv["expected"] = "closed", None
            return [T.NOT_INTERESTED], dbg
        if expected == "current_tool" and not conv["details"].get("current_tool") and re.search(r"(?i)\bskip\b", text):
            conv["details"]["current_tool"] = "skip"
            got.append("current_tool")
        if expected in got or (got and expected not in REQUIRED):
            return [_ask_next(conv, source)], dbg
        if got:  # gave other details but not the one asked
            return [_ask_next(conv, source)], dbg
        ans = _faq(u.faq_topic)
        if ans and u.intent in ("question", "interested"):
            return [ans, T.BACK_TO_FLOW.format(question=T.ASK[expected])], dbg
        conv["retries"] = conv.get("retries", 0) + 1
        if conv["retries"] >= 3:
            return [_handoff(conv, text)], dbg
        return [T.RETRY[expected]], dbg

    if st == "done":
        ans = _faq(u.faq_topic)
        if ans:
            return [ans], dbg
        if u.intent in ("interested", "greeting"):
            return [T.ALREADY_DONE], dbg
        return [], dbg

    # new / closed / paused
    if u.intent == "interested" or (st == "paused" and u.intent in ("answer", "greeting")):
        parts = []
        ans = _faq(u.faq_topic)
        if ans and u.faq_topic != "features":
            parts.append(ans)
        if _next_field(conv) and st != "paused":
            parts.append(T.START_COLLECT)
        parts.append(_ask_next(conv, source))
        return parts, dbg
    if u.intent == "question":
        return [_faq(u.faq_topic) or T.OFF_TOPIC, T.DEMO_CTA], dbg
    if u.intent == "greeting":
        return [T.GREETING], dbg
    if u.intent == "thanks":
        return [T.THANKS_REPLY], dbg
    if u.intent == "not_interested":
        conv["state"] = "closed"
        return [T.NOT_INTERESTED], dbg
    if not conv["details"].get("_offtopic"):  # say it once, then stay quiet
        conv["details"]["_offtopic"] = 1
        return [T.OFF_TOPIC], dbg
    return [], dbg


# ---------------- entry points used by the webhook server ----------------
def on_dm(igsid: str, text: str, ts: float, username: str | None = None, source: str = "dm") -> list[str]:
    conv = store.get(igsid)
    conv["last_in"] = ts
    if username:
        conv["username"] = username
    store.log_msg(igsid, "in", text)
    parts, dbg = decide(conv, text, source)
    store.save(conv)
    log.info("dm %s %s -> %s", igsid, dbg, conv["state"])
    if parts:
        reply = "\n\n".join(parts)
        meta.send_dm(igsid, reply, conv["last_in"])
        store.log_msg(igsid, "out", reply)
        return [reply]
    return []


def on_owner_reply(igsid: str) -> None:
    """Akshay replied by hand from the Instagram app: stop the bot for this chat."""
    conv = store.get(igsid)
    if conv["state"] not in ("opted_out",):
        conv["state"], conv["expected"] = "human", None
        store.save(conv)


def on_comment(comment_id: str, user_id: str, username: str, text: str) -> dict:
    conv = store.get(user_id)
    conv["username"] = username
    u, engine = brain.understand(text, None, "comment")
    out = {"engine": engine, "intent": u.intent, "public": None, "private": None}
    if conv["state"] == "opted_out" or u.intent in ("off_topic", "not_interested", "opt_out"):
        return out
    if u.intent == "thanks":
        out["public"] = T.COMMENT_PUBLIC_THANKS.format(username=username)
        meta.reply_comment(comment_id, out["public"])
        return out
    if u.intent == "human" or u.faq_topic == "unknown":
        _handoff(conv, f"[comment] {text}")
        store.save(conv)
        out["private"] = T.HANDOFF
        meta.private_reply(comment_id, T.HANDOFF)
        return out
    # interested / question / greeting
    last = conv["details"].get("_private_at", 0)
    if conv["state"] == "done":
        out["public"] = T.COMMENT_PUBLIC_DONE.format(username=username)
    elif time.time() - last <= PRIVATE_REPLY_COOLDOWN or conv["state"] in ("human", "collecting"):
        out["public"] = T.COMMENT_PUBLIC_RECENT.format(username=username)
    else:
        out["public"] = T.COMMENT_PUBLIC_INTERESTED.format(username=username)
    meta.reply_comment(comment_id, out["public"])
    if out["public"].endswith("📩") and "DM kiya" in out["public"]:
        answer = _faq(u.faq_topic) or T.COMMENT_DEFAULT_ANSWER
        out["private"] = T.COMMENT_PRIVATE_OPENER.format(answer=answer)
        meta.private_reply(comment_id, out["private"])
        conv["details"]["_private_at"] = time.time()
        store.log_msg(user_id, "out", out["private"])
    store.save(conv)
    return out
