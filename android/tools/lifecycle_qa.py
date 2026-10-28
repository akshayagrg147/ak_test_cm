"""System-level emulator checks after WorkflowUiTest. Never runs against a physical phone."""

import json
import os
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

from qa_fixture import PATH, ROOT, api, session

SERIAL = os.environ.get("AVEN_QA_SERIAL", "emulator-5580")
if SERIAL not in {"emulator-5580", "emulator-5582"}:
    raise RuntimeError("Only dedicated Aven QA emulators are allowed")
PKG = "com.aven.calls.debug"
fixture = json.loads(PATH.read_text())
client = session(fixture["phone"], fixture["password"])
report = []


def adb(*args, required=True):
    result = subprocess.run(
        ["/opt/homebrew/bin/adb", "-s", SERIAL, *args],
        check=False,
        capture_output=True,
        timeout=40,
    )
    if required and result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return result


def saved():
    rows, page = [], 1
    while True:
        result = api(
            client,
            "GET",
            "/phone-calls",
            params={"lead_id": fixture["lead_id"], "page": page},
        )
        rows.extend(result["items"])
        if len(rows) >= result["total"]:
            return rows
        page += 1


def check(name, condition):
    assert condition, name
    report.append({"case": name, "result": "passed"})
    report_name = (
        "lifecycle.json" if SERIAL == "emulator-5580" else "lifecycle-api36.json"
    )
    report_dir = Path(os.environ.get("AVEN_QA_REPORT_DIR", str(ROOT / "artifacts/android")))
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / report_name).write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print("PASS:", name, flush=True)


def eventually(predicate, seconds=55):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(2)
    return False


def launch():
    # sys.boot_completed can precede package availability after the first unlock.
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        result = adb(
            "shell",
            "am",
            "start",
            "-W",
            "-n",
            PKG + "/com.aven.calls.MainActivity",
            required=False,
        )
        if result.returncode == 0 and b"Error" not in result.stderr + result.stdout:
            return
        time.sleep(2)
    raise RuntimeError("The test app did not become available after unlock")


def incoming(answer=False):
    adb("emu", "gsm", "call", fixture["customer_phone"])
    time.sleep(2)
    if answer:
        adb("emu", "gsm", "accept", fixture["customer_phone"])
        time.sleep(3)
    adb("emu", "gsm", "cancel", fixture["customer_phone"])


def snapshot():
    folder = ROOT / (".local/android-probe-" + SERIAL)
    folder.mkdir(mode=0o700, exist_ok=True)
    for suffix in ["", "-wal", "-shm"]:
        result = adb(
            "exec-out",
            "run-as",
            PKG,
            "cat",
            "databases/aven-calls.db" + suffix,
            required=False,
        )
        path = folder / ("aven-calls.db" + suffix)
        if result.returncode == 0:
            path.write_bytes(result.stdout)
            path.chmod(0o600)
        elif path.exists():
            path.unlink()
    return sqlite3.connect(folder / "aven-calls.db")


def main():
    assert adb("shell", "getprop", "ro.kernel.qemu").stdout.strip() == b"1"
    before = len(saved())
    adb("shell", "input", "keyevent", "KEYCODE_HOME")
    incoming(answer=True)
    check(
        "Background incoming answered cellular-simulator call syncs",
        eventually(lambda: len(saved()) == before + 1),
    )
    newest = max(saved(), key=lambda row: datetime.fromisoformat(row["started_at"]))
    check(
        "Incoming direction, answered outcome and positive duration preserved",
        newest["direction"] == "incoming"
        and newest["result"] == "answered"
        and newest["duration"] > 0,
    )

    before = len(saved())
    adb("shell", "am", "force-stop", PKG)
    incoming()
    time.sleep(5)
    check(
        "Force-stopped app does not claim to run in the background",
        len(saved()) == before,
    )
    launch()
    check(
        "Opening after force-stop backfills the missed work call once",
        eventually(lambda: len(saved()) == before + 1),
    )

    adb("shell", "input", "keyevent", "KEYCODE_HOME")
    adb("shell", "svc", "wifi", "disable")
    adb("shell", "svc", "data", "disable")
    time.sleep(3)
    before = len(saved())
    incoming()
    time.sleep(24)
    adb("shell", "am", "force-stop", PKG)
    with snapshot() as db:
        queued = db.execute(
            "SELECT count(*) FROM calls WHERE state='pending'"
        ).fetchone()[0]
        integrity = db.execute("PRAGMA quick_check").fetchone()[0]
    check(
        "Offline call is committed in SQLite before network recovery",
        queued > 0 and integrity == "ok" and len(saved()) == before,
    )
    adb("shell", "svc", "wifi", "enable")
    adb("shell", "svc", "data", "enable")
    launch()
    check(
        "Offline queue survives process stop and uploads after reconnect",
        eventually(lambda: len(saved()) == before + 1),
    )

    before = len(saved())
    adb("shell", "pm", "revoke", PKG, "android.permission.READ_CALL_LOG")
    incoming()
    launch()
    time.sleep(6)
    check(
        "Revoked call-log permission prevents capture and preserves server records",
        len(saved()) == before,
    )
    adb("shell", "pm", "grant", PKG, "android.permission.READ_CALL_LOG")
    adb("shell", "am", "force-stop", PKG)
    launch()
    check(
        "Regranting permission resumes backfill without reinstalling",
        eventually(lambda: len(saved()) == before + 1),
    )

    before = len(saved())
    adb("shell", "pm", "revoke", PKG, "android.permission.POST_NOTIFICATIONS")
    launch()
    adb("shell", "input", "keyevent", "KEYCODE_HOME")
    incoming()
    check(
        "Notification denial does not discard background call metadata",
        eventually(lambda: len(saved()) == before + 1),
    )
    adb("shell", "pm", "grant", PKG, "android.permission.POST_NOTIFICATIONS")

    before = len(saved())
    adb("reboot")
    time.sleep(4)
    check(
        "Dedicated emulator reboots successfully",
        eventually(
            lambda: (
                adb(
                    "shell", "getprop", "sys.boot_completed", required=False
                ).stdout.strip()
                == b"1"
            ),
            120,
        ),
    )
    adb("shell", "wm", "dismiss-keyguard")
    launch()
    incoming()
    check(
        "Keystore session and scheduled sync recover after reboot and unlock",
        eventually(lambda: len(saved()) == before + 1),
    )

    before = len(saved())
    adb("shell", "input", "keyevent", "KEYCODE_HOME")
    adb("shell", "dumpsys", "battery", "unplug")
    adb("shell", "input", "keyevent", "KEYCODE_SLEEP")
    adb("shell", "dumpsys", "deviceidle", "force-idle")
    incoming()
    adb("shell", "dumpsys", "deviceidle", "unforce")
    adb("shell", "dumpsys", "battery", "reset")
    adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
    adb("shell", "wm", "dismiss-keyguard")
    launch()
    check(
        "Work-call reconciliation recovers after forced idle",
        eventually(lambda: len(saved()) == before + 1),
    )
    rows = saved()
    identities = [(row["device_id"], row["device_call_id"]) for row in rows]
    check(
        "Repeated recovery never creates duplicate device-call identities",
        len(identities) == len(set(identities)),
    )


try:
    main()
finally:
    adb("shell", "pm", "grant", PKG, "android.permission.READ_CALL_LOG", required=False)
    adb(
        "shell",
        "pm",
        "grant",
        PKG,
        "android.permission.POST_NOTIFICATIONS",
        required=False,
    )
    adb("shell", "svc", "wifi", "enable", required=False)
    adb("shell", "svc", "data", "enable", required=False)
    adb("shell", "dumpsys", "deviceidle", "unforce", required=False)
    adb("shell", "dumpsys", "battery", "reset", required=False)
