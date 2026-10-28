"""Provision/archive an isolated local-only emulator workspace. Never truncates a database."""

import argparse
import hashlib
import io
import json
import os
import secrets
import time
import wave
from pathlib import Path

import httpx
import pyotp

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / ".local/android-fixture.json"
BASE = "http://127.0.0.1:8010/api"


def session(phone, password):
    client = httpx.Client(timeout=30)
    client.headers["X-Requested-With"] = "TalkoCRM"
    response = client.post(
        BASE + "/auth/login", json={"phone": phone, "password": password}
    )
    response.raise_for_status()
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    return client


def api(client, method, path, **kwargs):
    response = client.request(method, BASE + path, **kwargs)
    response.raise_for_status()
    return response.json() if response.content else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["create", "verify", "archive", "otp"])
    action = parser.parse_args().action
    owner = session(os.environ["QA_OWNER_PHONE"], os.environ["QA_OWNER_PASSWORD"])
    if action == "create":
        if PATH.exists():
            raise RuntimeError(
                "Archive the previous isolated fixture before creating another"
            )
        numbers = [
            "+9197" + str(secrets.randbelow(90000000) + 10000000) for _ in range(4)
        ]
        password = secrets.token_urlsafe(20) + "!aA1"
        name = "Android emulator QA " + str(int(time.time()))
        created = api(
            owner,
            "POST",
            "/platform/organizations",
            json={
                "name": name,
                "admin": {
                    "name": "Emulator QA Admin",
                    "phone": numbers[0],
                    "password": password,
                    "role": "admin",
                },
            },
        )
        fixture = {
            "org_id": created["organization"]["id"],
            "name": name,
            "password": password,
            "admin_phone": numbers[0],
            "phone": numbers[1],
            "second_phone": numbers[2],
            "customer_phone": numbers[3],
            "server": "http://10.0.2.2:8010",
        }
        PATH.write_text(json.dumps(fixture))
        PATH.chmod(0o600)
        admin = session(numbers[0], password)
        for number in numbers[1:3]:
            api(
                admin,
                "POST",
                "/team",
                json={
                    "name": "Emulator QA Caller",
                    "phone": number,
                    "password": password,
                    "role": "telecaller",
                },
            )
        caller = session(numbers[1], password)
        lead = api(
            caller,
            "POST",
            "/leads",
            json={"name": "Emulator QA Customer", "phone": numbers[3]},
        )
        fixture["lead_id"] = lead["id"]
        PATH.write_text(json.dumps(fixture))
        print(
            "Created isolated emulator workspace; credentials saved privately, not printed"
        )
    else:
        fixture = json.loads(PATH.read_text())
        if action == "otp":
            if "otp_phone" not in fixture:
                admin = session(fixture["admin_phone"], fixture["password"])
                number = "+9197" + str(secrets.randbelow(90000000) + 10000000)
                api(
                    admin,
                    "POST",
                    "/team",
                    json={
                        "name": "Emulator QA Authenticator",
                        "phone": number,
                        "password": fixture["password"],
                        "role": "telecaller",
                    },
                )
                caller = session(number, fixture["password"])
                secret = api(
                    caller,
                    "POST",
                    "/auth/2fa/setup",
                    json={"password": fixture["password"]},
                )["secret"]
                api(
                    caller,
                    "POST",
                    "/auth/2fa/enable",
                    json={
                        "password": fixture["password"],
                        "code": pyotp.TOTP(secret).now(),
                    },
                )
                fixture.update(
                    otp_phone=number, otp_secret=secret, otp_step=int(time.time()) // 30
                )
                PATH.write_text(json.dumps(fixture))
            print("Isolated authenticator fixture ready; secret kept private")
        elif action == "archive":
            api(
                owner,
                "DELETE",
                "/platform/organizations/" + fixture["org_id"],
                params={"confirmation": fixture["name"]},
            )
            PATH.unlink()
            print(
                "Isolated emulator workspace archived; shared customer records preserved"
            )
        else:
            admin = session(fixture["admin_phone"], fixture["password"])
            calls = api(
                admin, "GET", "/phone-calls", params={"lead_id": fixture["lead_id"]}
            )
            files = api(admin, "GET", "/leads/" + fixture["lead_id"] + "/history")[
                "files"
            ]
            downloads = []
            for attachment in files:
                response = admin.get(BASE + "/files/" + attachment["id"])
                response.raise_for_status()
                with wave.open(io.BytesIO(response.content), "rb") as wav:
                    assert wav.getnchannels() == 1 and wav.getnframes() > 0
                downloads.append(
                    {
                        "bytes": len(response.content),
                        "sha256": hashlib.sha256(response.content).hexdigest(),
                    }
                )
            assert downloads, (
                "The emulator recording pipeline must produce downloadable audio"
            )
            assert len({row["sha256"] for row in downloads}) == len(downloads), (
                "Duplicate recording bytes were persisted"
            )
            assert all(len(call["recordings"]) <= 1 for call in calls["items"])
            print(
                json.dumps(
                    {
                        "server_call_count": calls["total"],
                        "recordings": downloads,
                        "duplicate_attachments": 0,
                        "audio_download_and_decode": "passed",
                    },
                    indent=2,
                )
            )


if __name__ == "__main__":
    main()
