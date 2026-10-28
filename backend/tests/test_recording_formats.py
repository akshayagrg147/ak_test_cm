from pathlib import Path

import pytest

from app.db import now
from app.files import content_type, validate_content
from conftest import make_lead


MEDIA = Path(__file__).parent / "fixtures" / "media"


def native_recording(brand=b"3gp4", fixture="aac-3gp4-native-meta.m4a"):
    raw = (MEDIA / fixture).read_bytes()
    return raw[:8] + brand + raw[12:]


def recording_call(caller):
    lead = make_lead(caller)
    response = caller.post(
        "/api/phone-calls/sync",
        json={
            "device_id": "native-container-regression",
            "calls": [{
                "device_call_id": "native-1",
                "phone": lead["phone"],
                "direction": "outgoing",
                "result": "answered",
                "started_at": now().isoformat(),
                "duration": 12,
            }],
        },
    )
    assert response.status_code == 200, response.text
    return lead, response.json()["entries"][0]["call_id"]


@pytest.mark.parametrize("brand", [b"3gp4", b"3gp6", b"mp41", b"mp42", b"M4A ", b"isom"])
def test_valid_native_mp4_audio_brands(brand):
    raw = native_recording(brand)
    mime = content_type(raw)
    assert mime == "audio/mp4"
    validate_content(raw, mime)


@pytest.mark.parametrize("brand,fixture", [
    (b"3gp4", "aac-3gp4.m4a"),
    (b"3gp4", "aac-3gp4-native-meta.m4a"),
    (b"mp41", "aac-3gp4-native-meta.m4a"),
], ids=["standard-3gp4", "native-3gp4", "native-mp41"])
def test_native_recording_upload_is_visible_and_private(env, brand, fixture):
    clients, _ = env
    caller = clients["caller"]
    lead, call_id = recording_call(caller)
    path = f"/api/leads/{lead['id']}/files"
    raw = native_recording(brand, fixture)

    def upload():
        return caller.post(
            path,
            data={"phone_call_id": call_id},
            files={"file": ("native-call.m4a", raw, "application/octet-stream")},
        )

    response = upload()
    assert response.status_code == 201, response.text
    record = response.json()
    assert record["mime"] == "audio/mp4" and record["size"] == len(raw)
    assert "storage_key" not in record
    assert upload().json()["id"] == record["id"]
    history = clients["admin"].get(f"/api/leads/{lead['id']}/history").json()
    assert [file["id"] for file in history["files"]] == [record["id"]]
    assert history["phone_calls"][0]["recording_state"] == "attached"
    assert history["phone_calls"][0]["recordings"][0]["id"] == record["id"]
    download = clients["admin"].get(f"/api/files/{record['id']}?inline=true")
    assert download.status_code == 200 and download.content == raw
    assert download.headers["content-type"].startswith("audio/mp4")
    assert download.headers["x-content-type-options"] == "nosniff"
    for role in ["caller2", "other"]:
        assert clients[role].get(f"/api/files/{record['id']}").status_code == 404


@pytest.mark.parametrize("kind", ["truncated-audio", "header-only", "video-only", "truncated-box", "bad-extended-size"])
def test_mp4_signature_alone_does_not_allow_invalid_recordings(env, kind):
    clients, _ = env
    caller = clients["caller"]
    lead, call_id = recording_call(caller)
    raw = {
        "truncated-audio": native_recording()[:80],
        "header-only": b"\x00\x00\x00\x18ftyp3gp4\x00\x00\x00\x00isom3gp4",
        "video-only": (MEDIA / "video-only.mp4").read_bytes(),
        "truncated-box": native_recording()[:-2],
        "bad-extended-size": b"\x00\x00\x00\x01ftyp3gp4\x00\x00\x00\x04",
    }[kind]
    response = caller.post(
        f"/api/leads/{lead['id']}/files",
        data={"phone_call_id": call_id},
        files={"file": ("native-call.m4a", raw, "audio/mp4")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_content"
    history = clients["admin"].get(f"/api/leads/{lead['id']}/history").json()
    assert history["files"] == []
    assert history["phone_calls"][0]["recording_state"] == "unavailable"
    assert history["phone_calls"][0]["recordings"] == []
