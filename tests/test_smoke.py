import json

import pytest
from fastapi.testclient import TestClient

from main import app
from utils import generate_qr_text, parse_qr_text


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def login(client, student_id="MA22_IT_02598", password="HendeAwku@1"):
    response = client.post("/login", data={"student_id": student_id, "password": password})
    assert response.status_code in (200, 303), response.text
    return response


def make_event(client, name):
    response = client.post(
        "/events",
        data={"name": name, "event_date": "2026-11-24", "venue": "Hall"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    event_id = int(response.headers["location"].split("/")[2])
    response = client.post(
        f"/events/{event_id}/status", data={"status": "open"}, follow_redirects=False
    )
    assert response.status_code == 303
    client.post(f"/events/{event_id}/select")
    return event_id


def make_student(client, student_id, last_name="Tadeo"):
    response = client.post(
        "/students",
        data={
            "student_id": student_id,
            "first_name": "Sebastian",
            "middle": "L.",
            "last_name": last_name,
            "program": "BSIT",
            "year": "3",
            "section": "A",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


def test_login_and_dashboard(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    login(client)
    response = client.get("/")
    assert response.status_code == 200
    assert "Dashboard" in response.text


def test_qr_json_round_trip():
    student = type(
        "S",
        (),
        {
            "student_id": "MA22-001",
            "first_name": "Sebastian",
            "middle": "L.",
            "last_name": "Tadeo",
            "program": "BSIT",
            "year": 3,
            "section": "A",
        },
    )()
    parsed = parse_qr_text(generate_qr_text(student))
    assert parsed["student_id"] == "MA22-001"
    assert parsed["year"] == 3
    assert parse_qr_text("Sebastian L. Tadeo BSIT 3A") is None


def test_event_scoped_scan_sequence(client):
    make_event(client, "Opening Ceremony")
    make_student(client, "MA22-001")

    first = client.post("/api/scan", json={"mode": "in", "student_id": "MA22-001"})
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "ok"
    assert first.json()["direction"] == "in"

    duplicate = client.post("/api/scan", json={"mode": "in", "student_id": "MA22-001"})
    assert duplicate.json()["status"] == "duplicate"

    checkout = client.post("/api/scan", json={"mode": "out", "student_id": "MA22-001"})
    assert checkout.json()["status"] == "ok"
    assert checkout.json()["direction"] == "out"

    twice = client.post("/api/scan", json={"mode": "out", "student_id": "MA22-001"})
    assert twice.json()["status"] == "already_checked_out"


def test_qr_scan_and_invalid_qr(client):
    payload = json.dumps(
        {
            "student_id": "MA22-002",
            "first_name": "Maria",
            "middle": "",
            "last_name": "Santos",
            "program": "BSCS",
            "year": 2,
            "section": "B",
        }
    )
    response = client.post("/api/scan", json={"mode": "in", "text": payload})
    assert response.json()["status"] == "not_registered"
    make_student(client, "MA22-002", "Santos")
    response = client.post("/api/scan", json={"mode": "in", "text": payload})
    assert response.json()["status"] == "ok"
    invalid = client.post("/api/scan", json={"mode": "in", "text": "not json"})
    assert invalid.json()["status"] == "invalid_qr"


def test_event_isolation(client):
    attendance = client.get("/api/attendance").json()
    assert sum(year["total"] for year in attendance) >= 2
    make_event(client, "Second Event")
    fresh = client.get("/api/attendance").json()
    assert fresh == []


def test_csv_preview_and_confirm(client):
    make_event(client, "CSV Event")
    csv_content = (
        "student_id,first_name,middle,last_name,program,year,section\n"
        "MA22-100,Ana,M.,Cruz,BSIT,3,A\n"
        "MA22-100,Dup,X.,Bad,BSIT,3,A\n"
        "MA22-101,No,Year,Bad,BSIT,x,A\n"
    )
    response = client.post(
        "/students/import/preview",
        files={"file": ("roster.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 200
    assert "1 ready, 2 with errors" in response.text
    batch_id = int(response.text.split('name="batch_id" value="')[1].split('"')[0])
    response = client.post(
        "/students/import/confirm", data={"batch_id": batch_id}, follow_redirects=False
    )
    assert response.status_code == 303
    students = client.get("/students?search=MA22-100")
    assert "Ana" in students.text
    assert "Bad" not in students.text


def test_export_and_audit(client):
    response = client.get("/download-csv?event_id=0")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    audit = client.get("/audit")
    assert audit.status_code == 200
    assert "Import" in audit.text or "Export" in audit.text


def test_permissions(client):
    response = client.post(
        "/accounts",
        data={"student_id": "SCAN-1", "password": "password123", "role": "scanner"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    client.get("/logout")
    login(client, "SCAN-1", "password123")
    assert client.get("/scan").status_code == 200
    assert client.get("/events").status_code == 403
