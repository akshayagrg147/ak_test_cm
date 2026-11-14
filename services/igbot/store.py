"""SQLite store: one row per Instagram user (conversation state) + leads + processed-event dedupe."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).with_name("data") / "agent.db"))

FIELDS = ["name", "team_size", "lead_sources", "current_tool"]  # the 3 qualifying questions (playbook Script B) + name
LEAD_COLS = ["name", "whatsapp", "team_size", "lead_sources", "current_tool", "demo_time"]


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        create table if not exists convo (
          igsid text primary key, username text, state text default 'new',
          expected text, details text default '{}', retries integer default 0,
          last_in real default 0, updated real default 0);
        create table if not exists leads (
          id integer primary key autoincrement, igsid text, username text,
          name text, whatsapp text, team_size text, current_tool text, demo_time text,
          source text, created real);
        create table if not exists seen (key text primary key, at real);
        create table if not exists log (
          id integer primary key autoincrement, igsid text, direction text, text text, at real);
        """
    )
    if "lead_sources" not in [r[1] for r in c.execute("pragma table_info(leads)")]:
        c.execute("alter table leads add column lead_sources text")
    return c


def get(igsid: str) -> dict:
    with _conn() as c:
        r = c.execute("select * from convo where igsid=?", (igsid,)).fetchone()
        if not r:
            c.execute("insert into convo(igsid, updated) values(?,?)", (igsid, time.time()))
            r = c.execute("select * from convo where igsid=?", (igsid,)).fetchone()
    d = dict(r)
    d["details"] = json.loads(d["details"] or "{}")
    return d


def save(conv: dict) -> None:
    with _conn() as c:
        c.execute(
            "update convo set username=?, state=?, expected=?, details=?, retries=?, last_in=?, updated=? where igsid=?",
            (conv.get("username"), conv["state"], conv.get("expected"), json.dumps(conv["details"], ensure_ascii=False),
             conv.get("retries", 0), conv.get("last_in", 0), time.time(), conv["igsid"]),
        )


def first_seen(key: str) -> bool:
    """True the first time a webhook event key is seen (Meta retries deliveries)."""
    with _conn() as c:
        try:
            c.execute("insert into seen values(?,?)", (key, time.time()))
            return True
        except sqlite3.IntegrityError:
            return False


def add_lead(conv: dict, source: str) -> dict:
    d = conv["details"]
    row = {"igsid": conv["igsid"], "username": conv.get("username") or "", **{f: d.get(f, "") for f in LEAD_COLS},
           "source": source, "created": time.time()}
    with _conn() as c:
        c.execute(
            "insert into leads(igsid, username, name, whatsapp, team_size, lead_sources, current_tool, demo_time,"
            " source, created) values(:igsid,:username,:name,:whatsapp,:team_size,:lead_sources,:current_tool,"
            ":demo_time,:source,:created)", row)
    return row


def log_msg(igsid: str, direction: str, text: str) -> None:
    with _conn() as c:
        c.execute("insert into log(igsid, direction, text, at) values(?,?,?,?)", (igsid, direction, text, time.time()))


def leads() -> list[dict]:
    with _conn() as c:
        return [dict(r) for r in c.execute("select * from leads order by id")]


def paused() -> list[dict]:
    with _conn() as c:
        return [dict(r) for r in c.execute("select igsid, username, updated from convo where state='human'")]


def set_state(igsid: str, state: str) -> None:
    with _conn() as c:
        c.execute("update convo set state=?, expected=null, updated=? where igsid=?", (state, time.time(), igsid))


def last_out(igsid: str, within: float = 600) -> list[str]:
    with _conn() as c:
        return [r[0] for r in c.execute(
            "select text from log where igsid=? and direction='out' and at>? order by id desc limit 5",
            (igsid, time.time() - within))]
