import io
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from openpyxl import Workbook
from sqlalchemy import select

from app.db import SessionLocal, now
from app.models import Assignment, Lead
from conftest import make_lead


def upload(client, content, filename="leads.csv", commit=True):
    return client.post("/api/imports?commit=" + str(commit).lower(), files={"file": (filename, content)})


def test_creation_ownership_and_international_phones(env):
    c, ids = env
    for index, role in enumerate(["admin", "manager", "caller", "caller2"]):
        lead = make_lead(c[role], phone=f"981001000{index}")
        assert lead["owner_id"] == (ids[role] if role.startswith("caller") else None)
    lead = make_lead(c["admin"], phone="+14155552671")
    assert lead["phone"] == "+14155552671"
    local = c["admin"].post("/api/leads", json={"name": "Indian landline", "phone": "(415)555-2671"})
    assert local.status_code == 201 and local.json()["phone"] == "+914155552671"
    assert c["admin"].post("/api/leads", json={"name": "Duplicate", "phone": "+1 415 555 2671"}).status_code == 409


def test_import_preview_commit_replay_duplicates_and_ownership(env):
    c, ids = env
    csv = "\ufeffCustomer Name,Mobile,city\nAlice Example,9810001234,Pune\nBob Example,9810001235,Mumbai\nDuplicate,9810001234,Pune\nBad row,abc,Delhi\n,,\n".encode(
        "utf-8"
    )
    preview = upload(c["caller"], csv, commit=False)
    assert preview.status_code == 200, preview.text
    assert preview.json()["accepted"] == 2 and preview.json()["duplicates"] == 1 and preview.json()["invalid"] == 1
    assert c["admin"].get("/api/leads").json()["total"] == 0
    r = upload(c["caller"], csv)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 2 and r.json()["owner"] == ids["caller"]
    assert all(lead["owner_id"] == ids["caller"] for lead in c["admin"].get("/api/leads").json()["items"])
    retry = upload(c["caller"], csv).json()
    assert retry["replayed"] and retry["imported"] == 2
    assert c["admin"].get("/api/leads").json()["total"] == 2
    assert c["admin"].get("/api/imports/" + r.json()["import_id"] + "/errors").status_code == 200
    assert c["other"].get("/api/imports/" + r.json()["import_id"] + "/errors").status_code == 404


@pytest.mark.parametrize(
    "content,filename,code",
    [
        (b"", "leads.csv", "empty_file"),
        (b"name,mobile,phone\nA,9810001234,9810001234", "a.csv", "duplicate_headers"),
        (b"name,city\nCustomer,Pune", "a.csv", "missing_columns"),
        (b"name,phone,owner_id\nCustomer,9810001234,forged", "a.csv", "forged_ownership"),
        (b"name,phone,org_id\nCustomer,9810001234,forged", "a.csv", "forged_ownership"),
        (b"name,phone,banana\nCustomer,9810001234,x", "a.csv", "unknown_columns"),
        (b"junk", "a.xls", "unsupported_file"),
        (b"not a zip", "a.xlsx", "malformed_file"),
        (b"\xff\xfe", "a.csv", "malformed_file"),
        (b'name,phone\n"unterminated', "a.csv", "malformed_file"),
    ],
)
def test_invalid_import_files(env, content, filename, code):
    c, _ = env
    r = upload(c["caller"], content, filename)
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == code
    assert c["admin"].get("/api/leads").json()["total"] == 0


def test_import_limits_and_xlsx_numeric_phones(env):
    c, _ = env
    r = upload(c["admin"], b"x" * (10 * 1024 * 1024 + 1))
    assert r.status_code == 413, r.text
    r = upload(c["admin"], b"name,phone\n" + b"Customer,9810001234\n" * 10001)
    assert r.status_code == 422
    wb = Workbook()
    ws = wb.active
    ws.append(["Full name", "Contact number", "city"])
    ws.append(["Numeric Customer", 9810001234, "Pune"])
    ws.append(["Zero Prefixed", "09810001235", "Mumbai"])
    ws.append(["Formula row", "=1+2", "Delhi"])
    data = io.BytesIO()
    wb.save(data)
    r = upload(c["admin"], data.getvalue(), "leads.xlsx")
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 2 and r.json()["invalid"] == 1
    assert all(lead["owner_id"] is None for lead in c["admin"].get("/api/leads").json()["items"])


def test_partially_invalid_csv_shape_and_duplicate_existing(env):
    c, _ = env
    make_lead(c["admin"])
    r = upload(
        c["manager"], b"name,phone\nExisting,9810001234\nMalformed,9810001235,extra\nOkay Customer,9810001236"
    ).json()
    assert (r["imported"], r["duplicates"], r["invalid"]) == (1, 1, 1)


def test_concurrent_import_idempotency(env):
    c, _ = env
    raw = b"name,phone\nConcurrent Customer,9810001234"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: upload(c["caller"], raw).json(), range(2)))
    assert sorted(bool(r.get("replayed")) for r in results) == [False, True]
    assert c["admin"].get("/api/leads").json()["total"] == 1


def test_distribution_zero_one_many_and_concurrent(env):
    c, ids = env
    leads = [make_lead(c["admin"], phone=f"98100012{i:02d}") for i in range(9)]
    for key in ["caller", "caller2"]:
        assert c["admin"].patch("/api/team/" + ids[key], json={"active": False}).status_code == 200
    assert c["admin"].post("/api/leads/distribute").json()["assigned"] == 0
    c["admin"].patch("/api/team/" + ids["caller"], json={"active": True})
    r = c["admin"].post("/api/leads/distribute").json()
    assert r["assigned"] == 9 and r["distribution"][ids["caller"]] == 9
    c["admin"].patch("/api/team/" + ids["caller2"], json={"active": True})
    for i in range(9):
        make_lead(c["manager"], phone=f"98100013{i:02d}")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: c["admin"].post("/api/leads/distribute").json(), range(2)))
    assert sum(r["assigned"] for r in results) == 9
    with SessionLocal() as db:
        assignments = list(db.scalars(select(Assignment).where(Assignment.source == "round_robin")))
        assert len(assignments) == 18
    counts = [
        sum(lead["owner_id"] == ids[k] for lead in c["admin"].get("/api/leads?size=100").json()["items"])
        for k in ["caller", "caller2"]
    ]
    assert sorted(counts) == [5, 13] or sorted(counts) == [4, 14]
    assert c["admin"].get("/api/leads/" + leads[0]["id"]).json()["owner_id"] == ids["caller"]


def test_queue_priority_dnd_outcome_followup_and_handoff(env):
    c, ids = env
    fresh = make_lead(c["caller"], phone="9810001234")
    overdue = make_lead(c["caller"], phone="9810001235")
    old = make_lead(c["caller"], phone="9810001236")
    with SessionLocal.begin() as db:
        db.get(Lead, overdue["id"]).follow_up = now() - timedelta(hours=1)
        db.get(Lead, overdue["id"]).status = "follow-up"
        db.get(Lead, overdue["id"]).last_contact = now() - timedelta(hours=2)
        db.get(Lead, old["id"]).created_at = now() - timedelta(days=4)
    assert [lead["id"] for lead in c["caller"].get("/api/leads").json()["items"]] == [
        overdue["id"],
        old["id"],
        fresh["id"],
    ]
    path = "/api/leads/" + fresh["id"] + "/outcomes"
    assert c["caller"].post(path, json={"outcome": "follow-up", "request_id": "missing-time"}).status_code == 422
    future = (now() + timedelta(days=1)).isoformat()
    payload = {"outcome": "follow-up", "follow_up": future, "duration": 120, "request_id": "outcome-unique"}
    r = c["caller"].post(path, json=payload)
    assert r.status_code == 201, r.text
    assert c["caller"].post(path, json=payload).json()["id"] == r.json()["id"]
    assert len(c["caller"].get("/api/leads/" + fresh["id"] + "/history").json()["manual_calls"]) == 1
    c["caller"].patch("/api/leads/" + fresh["id"], json={"dnd": True})
    assert c["caller"].post(path, json={"outcome": "converted", "request_id": "dnd-new-request"}).status_code == 409
    c["caller"].patch("/api/leads/" + fresh["id"], json={"dnd": False})
    lost = {
        "outcome": "lost",
        "notes": "Customer postponed the project",
        "manager_id": ids["manager"],
        "request_id": "lost-request-123",
    }
    assert c["caller"].post(path, json=lost).status_code == 201
    assert c["caller"].get("/api/leads/" + fresh["id"]).status_code == 404
    lead = c["admin"].get("/api/leads/" + fresh["id"]).json()
    assert lead["owner_id"] == ids["manager"] and lead["follow_up"] is None and lead["reported_by"] == ids["caller"]
    assert c["admin"].get("/api/leads?status=lost").json()["total"] == 1


def test_member_removal_requires_manager_handoff(env):
    c, ids = env
    lead = make_lead(c["caller"])
    path = "/api/team/" + ids["caller"] + "?confirmation=Caller%20User"
    assert c["admin"].delete(path).status_code == 422
    assert c["admin"].delete(path + "&manager_id=" + ids["other"]).status_code == 404
    assert c["admin"].delete(path + "&manager_id=" + ids["manager"]).status_code == 200
    assert c["admin"].get("/api/leads/" + lead["id"]).json()["owner_id"] == ids["manager"]
    assert c["caller"].get("/api/leads").status_code == 401


def test_merge_preserves_all_relationships_and_files(env):
    c, ids = env
    primary = make_lead(c["caller"])
    duplicate = make_lead(c["caller"], phone="9810001235", notes="Original context", interests=["generic"])
    note = c["caller"].post("/api/leads/" + duplicate["id"] + "/notes", json={"text": "Important note"}).json()
    call_data = {
        "device_id": "test-device-123",
        "calls": [
            {
                "device_call_id": "1",
                "phone": duplicate["phone"],
                "direction": "outgoing",
                "result": "answered",
                "started_at": now().isoformat(),
                "duration": 120,
            }
        ],
    }
    assert c["caller"].post("/api/phone-calls/sync", json=call_data).json()["created"] == 1
    pc = c["caller"].get("/api/phone-calls").json()["items"][0]
    import wave

    audio = io.BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\0" * 1600)
    raw = audio.getvalue()
    file = c["caller"].post(
        "/api/leads/" + duplicate["id"] + "/files",
        data={"phone_call_id": pc["id"], "note_id": note["id"]},
        files={"file": ("../../recording.wav", raw, "audio/wav")},
    )
    assert file.status_code == 201, file.text
    c["caller"].post(
        "/api/leads/" + duplicate["id"] + "/outcomes",
        json={
            "outcome": "converted",
            "phone_call_id": pc["id"],
            "request_id": "merge-call-linked",
            "order_value": "150.25",
        },
    )
    task = c["caller"].post(
        "/api/tasks",
        json={"title": "Merged task", "lead_id": duplicate["id"], "due_at": (now() + timedelta(days=1)).isoformat()},
    )
    assert task.status_code == 201
    assert c["other"].post("/api/leads/" + primary["id"] + "/merge/" + duplicate["id"]).status_code == 404
    r = c["admin"].post("/api/leads/" + primary["id"] + "/merge/" + duplicate["id"])
    assert r.status_code == 200, r.text
    h = c["caller"].get("/api/leads/" + primary["id"] + "/history").json()
    assert (
        len(h["notes"]) == 2
        and len(h["manual_calls"]) == 1
        and len(h["phone_calls"]) == 1
        and len(h["tasks"]) == 1
        and len(h["files"]) == 1
        and len(h["assignments"]) >= 2
    )
    assert c["caller"].get("/api/files/" + file.json()["id"]).content == raw
    assert c["caller"].get("/api/leads/" + duplicate["id"]).status_code == 404
    assert c["other"].get("/api/files/" + file.json()["id"]).status_code == 404
    c["admin"].post("/api/leads/assign", json={"lead_ids": [primary["id"]], "owner_id": ids["caller2"]})
    assert c["caller"].get("/api/files/" + file.json()["id"]).status_code == 404


def test_phone_sync_four_calls_retry_device_scope_ambiguity_and_reassignment(env):
    c, ids = env
    lead = make_lead(c["caller"])
    entries = [
        {
            "device_call_id": str(i),
            "phone": lead["phone"],
            "direction": "incoming" if i % 2 else "outgoing",
            "result": "answered",
            "started_at": (now() - timedelta(minutes=i + 1)).isoformat(),
            "duration": 45 + i,
        }
        for i in range(4)
    ]
    entries.append({**entries[0], "device_call_id": "personal", "phone": "+919810999999"})
    body = {"device_id": "phone-installation-1", "calls": entries}
    r = c["caller"].post("/api/phone-calls/sync", json=body).json()
    assert r["created"] == 4 and r["excluded"] == 1
    assert c["caller"].post("/api/phone-calls/sync", json=body).json()["updated"] == 4
    assert c["caller"].get("/api/phone-calls").json()["total"] == 4
    assert (
        c["caller"]
        .post("/api/phone-calls/sync", json={**body, "device_id": "phone-installation-2", "calls": entries[:1]})
        .json()["created"]
        == 1
    )
    make_lead(c["caller"], name="Ambiguous second record", allow_duplicate=True)
    assert c["caller"].post("/api/phone-calls/sync", json=body).json()["ambiguous"] == 4
    c["admin"].post("/api/leads/assign", json={"lead_ids": [lead["id"]], "owner_id": ids["caller2"]})
    assert c["caller"].get("/api/phone-calls").json()["total"] == 0
    assert c["admin"].get("/api/phone-calls").json()["total"] == 5
    assert c["other"].get("/api/phone-calls").json()["total"] == 0


def test_exports_formula_injection_and_saved_view_privacy(env):
    c, _ = env
    make_lead(c["caller"], name='=HYPERLINK("https://evil.invalid")')
    csv = c["caller"].get("/api/leads/export").text
    assert "'=HYPERLINK" in csv and "'+919810001234" in csv
    saved = c["caller"].post(
        "/api/saved-views", json={"name": "My fresh leads", "filters": {"status": "new"}, "kind": "leads"}
    )
    assert saved.status_code == 201
    assert c["caller2"].get("/api/saved-views").json() == []
    assert c["caller2"].delete("/api/saved-views/" + saved.json()["id"]).status_code == 404
    assert c["caller"].get("/api/leads?status=converted").json()["total"] == 0


def test_custom_fields_validation_and_stage_in_use(env):
    c, _ = env
    field = c["admin"].post(
        "/api/definitions",
        json={
            "kind": "field",
            "key": "sector",
            "label": "Sector",
            "config": {"type": "select", "required": True, "options": ["Education", "Retail"]},
        },
    )
    assert field.status_code == 201
    for custom in [{}, {"sector": "Unknown"}, {"forged": "yes"}]:
        assert (
            c["caller"]
            .post("/api/leads", json={"name": "Test Customer", "phone": "9810001234", "custom": custom})
            .status_code
            == 422
        )
    lead = make_lead(c["caller"], custom={"sector": "Retail"})
    stage = (
        c["admin"]
        .post(
            "/api/definitions",
            json={
                "kind": "stage",
                "key": "negotiation",
                "label": "Negotiation",
                "config": {"color": "#127456", "closed": False, "won": False},
            },
        )
        .json()
    )
    assert c["admin"].patch("/api/leads/" + lead["id"], json={"stage": "negotiation"}).status_code == 200
    assert c["admin"].delete("/api/definitions/" + stage["id"]).status_code == 409
    assert c["admin"].delete("/api/definitions/" + stage["id"] + "?migrate_to=qualified").status_code == 200
    assert c["admin"].get("/api/leads/" + lead["id"]).json()["stage"] == "qualified"
