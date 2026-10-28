"""Smoke a dedicated development Compose stack, including restart persistence.

Run only against a disposable QA stack already built and explicitly seeded.
No production credentials or reference resources are used.
"""

import argparse
import base64
import json
import secrets
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--project", required=True)
parser.add_argument("--env-file", required=True)
parser.add_argument("--override", required=True)
parser.add_argument("--url", default="http://localhost:18080")
parser.add_argument("--report", default="artifacts/qa-final/container-tests.txt")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
compose = [
    "docker",
    "compose",
    "-p",
    args.project,
    "--env-file",
    args.env_file,
    "-f",
    "compose.yaml",
    "-f",
    args.override,
]
report = []


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    report.append("PASS: " + message)


def run(*command):
    return subprocess.run(
        [*compose, *command], cwd=root, check=True, text=True, capture_output=True
    ).stdout


def wait_healthy():
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            response = httpx.get(args.url + "/api/health", timeout=3)
            if response.is_success and response.json().get("worker") == "ok":
                return
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(0.5)
    raise AssertionError("Container API and worker did not become healthy")


# Refuse a production stack before creating any fixtures or restarting it.
environment = run(
    "exec",
    "-T",
    "api",
    "python",
    "-c",
    "from app.config import settings; print(settings.environment)",
).strip()
if environment != "development" or not args.project.startswith("aven-"):
    raise SystemExit("Use a dedicated aven-* development QA stack")
wait_healthy()
check(True, "isolated API, PostgreSQL and worker are healthy")
password = "LocalCRM!2026"
headers = {"X-Requested-With": "TalkoCRM"}
with (
    httpx.Client(base_url=args.url, headers=headers, timeout=45) as owner,
    httpx.Client(base_url=args.url, headers=headers, timeout=45) as admin,
):
    response = owner.post(
        "/api/auth/login", json={"phone": "+919900000001", "password": password}
    )
    response.raise_for_status()
    owner.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    phone = "+9197" + str(secrets.randbelow(90000000) + 10000000)
    name = "Container restart QA " + uuid4().hex[:8]
    created = owner.post(
        "/api/platform/organizations",
        json={
            "name": name,
            "admin": {
                "name": "QA Administrator",
                "phone": phone,
                "password": password,
                "role": "admin",
            },
        },
    )
    created.raise_for_status()
    org_id = created.json()["organization"]["id"]
    try:
        response = admin.post(
            "/api/auth/login", json={"phone": phone, "password": password}
        )
        response.raise_for_status()
        admin.headers["Authorization"] = "Bearer " + response.json()["access_token"]
        cookie = response.headers.get("set-cookie", "").lower()
        check(
            "httponly" in cookie and "samesite=strict" in cookie,
            "browser refresh cookie is HttpOnly and SameSite=Strict",
        )
        html = admin.get("/app/leads")
        check(
            html.status_code == 200
            and 'type="module"' in html.text
            and "/assets/" in html.text
            and "/@vite/" not in html.text,
            "nginx serves built assets and SPA deep links",
        )
        check(
            "frame-ancestors" in html.headers.get("content-security-policy", "")
            and html.headers.get("x-content-type-options") == "nosniff",
            "nginx security headers are present",
        )
        response = admin.post(
            "/api/leads",
            json={
                "name": "Restart persistence customer",
                "phone": "+9198" + phone[-8:],
                "interests": ["CRM support", "उत्पाद"],
            },
        )
        response.raise_for_status()
        lead_id = response.json()["id"]
        raw = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR4nGMUCTjBAAJMYJKBgQEAEkIBMLmziVsAAAAASUVORK5CYII="
        )
        file = admin.post(
            f"/api/leads/{lead_id}/files",
            files={"file": ("restart.png", raw, "image/png")},
        )
        file.raise_for_status()
        file_id = file.json()["id"]
        run("restart", "api", "worker", "web")
        wait_healthy()
        response = admin.post("/api/auth/refresh")
        response.raise_for_status()
        admin.headers["Authorization"] = "Bearer " + response.json()["access_token"]
        check(
            response.json()["organization"]["id"] == org_id,
            "rotating refresh session survives container restart",
        )
        persisted = admin.get("/api/leads/" + lead_id)
        check(
            persisted.is_success
            and persisted.json()["interests"] == ["CRM support", "उत्पाद"],
            "database records and Unicode fields survive restart",
        )
        check(
            admin.get("/api/files/" + file_id).content == raw,
            "private storage file survives restart byte-for-byte",
        )
        check(
            admin.get("/api/health").json()["worker"] == "ok",
            "restarted worker publishes a current heartbeat",
        )
        check(
            admin.post("/api/auth/logout").is_success
            and admin.post("/api/auth/refresh").status_code == 401,
            "logout revokes the persisted refresh session",
        )
    finally:
        removed = owner.delete(
            "/api/platform/organizations/" + org_id, params={"confirmation": name}
        )
        check(
            removed.is_success,
            "only the smoke-test organization is archived after verification",
        )
state = json.loads(run("ps", "--format", "json").splitlines()[0])
check(bool(state), "Compose reports running services after the drill")
report_path = Path(args.report)
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text("\n".join(report) + "\n")
print("\n".join(report))
