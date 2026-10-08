import json
from pathlib import Path

from fastapi.testclient import TestClient


def test_register_login_bio_stays_encrypted_on_disk(client: TestClient, tmp_path: Path) -> None:
    created = client.post(
        "/v1/auth/register",
        json={
            "username": "vlad_home",
            "password": "correct-horse-battery",
            "profile": {"full_name": "Vlad Lundyshev", "phone": "+15550199", "email": "vlad@example.com"},
        },
    )
    assert created.status_code == 200, created.text

    on_disk = next(tmp_path.glob("*.json")).read_text(encoding="utf-8")
    assert "Vlad Lundyshev" not in on_disk
    assert "+15550199" not in on_disk
    assert "vlad@example.com" not in on_disk
    blob = json.loads(on_disk)
    assert blob["profile_blob"]["alg"] == "AES-256-GCM"
    assert "password_hash" in blob and blob["password_hash"].startswith("$argon2")

    bio = client.get("/v1/bio")
    assert bio.status_code == 200
    assert bio.json()["profile"]["full_name"] == "Vlad Lundyshev"

    client.post("/v1/auth/logout")
    assert client.get("/v1/bio").status_code == 401

    bad = client.post("/v1/auth/login", json={"username": "vlad_home", "password": "wrong-password-1"})
    assert bad.status_code == 401

    ok = client.post("/v1/auth/login", json={"username": "vlad_home", "password": "correct-horse-battery"})
    assert ok.status_code == 200
    saved = client.put("/v1/bio", json={"profile": {"city": "Lisbon", "full_name": "Vlad Lundyshev"}})
    assert saved.status_code == 200
    latest = client.get("/v1/bio")
    assert latest.json()["profile"]["city"] == "Lisbon"
    assert "Lisbon" not in next(tmp_path.glob("*.json")).read_text(encoding="utf-8")


def test_existing_telemetry_routes_stay_public(client: TestClient) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    login_page = client.get("/account/login")
    assert login_page.status_code == 200
    devices = client.get("/v1/devices")
    assert devices.status_code == 200
    kinds = {d["kind"] for d in devices.json()["devices"]}
    assert {"climate", "air_quality", "light", "motion"} <= kinds
    assert len(devices.json()["devices"]) >= 7
