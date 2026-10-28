"""Run instrumentation only against the dedicated Aven emulator; do not touch attached phones."""

import json
import os
import subprocess
from pathlib import Path

from qa_fixture import session

ROOT = Path(__file__).resolve().parents[2]
fixture = json.loads((ROOT / ".local/android-fixture.json").read_text())
admin = session(fixture["admin_phone"], fixture["password"])
fixture["admin_token"] = admin.headers["Authorization"].removeprefix("Bearer ")
(ROOT / ".local/android-fixture.json").write_text(json.dumps(fixture))
serial = os.environ.get("AVEN_QA_SERIAL", "emulator-5580")
if serial not in {"emulator-5580", "emulator-5582"}:
    raise RuntimeError("Only the dedicated Aven QA emulators are allowed")
command = [
    "/opt/homebrew/bin/adb",
    "-s",
    serial,
    "shell",
    "am",
    "instrument",
    "-w",
    "-r",
]
test_class = os.environ.get("AVEN_QA_TEST_CLASS")
if test_class:
    command.extend(["-e", "class", test_class])
for key in [
    "server",
    "phone",
    "password",
    "admin_phone",
    "second_phone",
    "customer_phone",
    "otp_phone",
    "otp_secret",
    "otp_step",
    "admin_token",
]:
    command.extend(["-e", key, str(fixture[key])])
command.append("com.aven.calls.debug.test/androidx.test.runner.AndroidJUnitRunner")
result = subprocess.run(
    command, check=False, capture_output=True, text=True, timeout=180
)
output = result.stdout + result.stderr
for key in [
    "password",
    "phone",
    "admin_phone",
    "second_phone",
    "customer_phone",
    "otp_phone",
    "otp_secret",
    "admin_token",
]:
    output = output.replace(str(fixture[key]), "[QA fixture]")
name = "device-tests.txt" if serial == "emulator-5580" else "device-tests-api36.txt"
if test_class:
    name = "device-" + test_class.rsplit(".", 1)[-1] + ".txt"
report_dir = Path(os.environ.get("AVEN_QA_REPORT_DIR", str(ROOT / "artifacts/android")))
report_dir.mkdir(parents=True, exist_ok=True)
(report_dir / name).write_text(output)
print(output)
if (
    result.returncode
    or "FAILURES!!!" in output
    or "INSTRUMENTATION_FAILED" in output
    or "OK (" not in output
):
    raise SystemExit(1)
