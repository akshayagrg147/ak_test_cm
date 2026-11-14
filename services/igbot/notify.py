"""Sends leads/handoffs to the Google Sheet (Apps Script web app), which also emails Akshay.
Always also appends to data/leads.csv so nothing is lost if the sheet is down."""
from __future__ import annotations

import csv
import json
import logging
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger("notify")
CSV = Path(__file__).with_name("data") / "leads.csv"
COLS = ["type", "created", "username", "name", "team_size", "lead_sources", "current_tool", "whatsapp", "source", "message"]


def push(kind: str, row: dict, summary: str) -> None:
    rec = {"type": kind, **{k: row.get(k, "") for k in COLS if k != "type"}, "summary": summary}
    ist = timezone(timedelta(hours=5, minutes=30))
    rec["created"] = datetime.fromtimestamp(float(rec["created"] or 0) or datetime.now().timestamp(), ist).strftime("%Y-%m-%d %H:%M IST")
    CSV.parent.mkdir(exist_ok=True)
    new = not CSV.exists()
    with CSV.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(rec)
    log.info("NOTIFY %s", summary)

    if kind == "lead":
        _push_viacrm(row)

    url = os.getenv("SHEET_WEBHOOK_URL")
    if not url or os.getenv("DRY_RUN", "1") != "0":
        return
    body = json.dumps({**rec, "secret": os.getenv("SHEET_WEBHOOK_SECRET", "")}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(req, timeout=20).read()
    except Exception as e:
        log.error("Sheet webhook failed (lead kept in leads.csv): %s", e)


def _push_viacrm(row: dict) -> None:
    """Create the lead inside ViaCRM (Studio -> Connections -> Lead capture -> Website integration)."""
    url, token = os.getenv("VIACRM_CAPTURE_URL"), os.getenv("VIACRM_CAPTURE_TOKEN")
    if not url or not token or os.getenv("DRY_RUN", "1") != "0":
        return
    v = lambda k: "-" if row.get(k) in (None, "", "skip") else row.get(k)
    body = {
        "id": f"ig-{row.get('igsid', '')}-{int(float(row.get('created') or 0))}",
        "name": row.get("name", ""),
        "phone": row.get("whatsapp", ""),
        "message": (f"Instagram @{v('username')} | team size {v('team_size')} | leads from: {v('lead_sources')} | "
                    f"leads kept in: {v('current_tool')}"),
        "source": "instagram",
    }
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Webhook-Token": token})
    try:
        urllib.request.urlopen(req, timeout=20).read()
        log.info("lead pushed to ViaCRM")
    except Exception as e:
        log.error("ViaCRM capture failed (lead kept in leads.csv): %s", e)
