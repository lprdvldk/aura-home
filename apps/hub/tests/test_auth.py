from __future__ import annotations

import asyncio
import json
from pathlib import Path

from aiohttp.test_utils import TestClient, TestServer

from smarthouse_hub.config import load_house_config
from smarthouse_hub.crypto_vault import UserVault
from smarthouse_hub.http_app import create_http_app
from smarthouse_hub.store import HouseStore


def _app(tmp_path: Path):
    config = Path(__file__).resolve().parents[3] / "config" / "house.json"
    return create_http_app(HouseStore(load_house_config(config)), UserVault(tmp_path))


def test_register_login_bio_stays_encrypted_on_disk(tmp_path: Path) -> None:
    app = _app(tmp_path)

    async def run() -> None:
        async with TestClient(TestServer(app)) as client:
            created = await client.post(
                "/v1/auth/register",
                json={
                    "username": "vlad_home",
                    "password": "correct-horse-battery",
                    "profile": {"full_name": "Vlad Lundyshev", "phone": "+15550199", "email": "vlad@example.com"},
                },
            )
            assert created.status == 200, await created.text()

            secret = tmp_path.read_text() if False else ""
            on_disk = next(tmp_path.glob("*.json")).read_text(encoding="utf-8")
            assert "Vlad Lundyshev" not in on_disk
            assert "+15550199" not in on_disk
            assert "vlad@example.com" not in on_disk
            blob = json.loads(on_disk)
            assert blob["profile_blob"]["alg"] == "AES-256-GCM"
            assert "password_hash" in blob and blob["password_hash"].startswith("$argon2")

            denied = await client.get("/v1/bio")
            # cookie from register should already authenticate this same client
            assert denied.status == 200
            bio = await denied.json()
            assert bio["profile"]["full_name"] == "Vlad Lundyshev"

            await client.post("/v1/auth/logout")
            assert (await client.get("/v1/bio")).status == 401

            bad = await client.post("/v1/auth/login", json={"username": "vlad_home", "password": "wrong-password-1"})
            assert bad.status == 401

            ok = await client.post(
                "/v1/auth/login", json={"username": "vlad_home", "password": "correct-horse-battery"}
            )
            assert ok.status == 200
            saved = await client.put("/v1/bio", json={"profile": {"city": "Lisbon", "full_name": "Vlad Lundyshev"}})
            assert saved.status == 200
            latest = await client.get("/v1/bio")
            assert (await latest.json())["profile"]["city"] == "Lisbon"
            assert "Lisbon" not in next(tmp_path.glob("*.json")).read_text(encoding="utf-8")

    asyncio.run(run())


def test_existing_telemetry_routes_stay_public(tmp_path: Path) -> None:
    app = _app(tmp_path)

    async def run() -> None:
        async with TestClient(TestServer(app)) as client:
            health = await client.get("/health")
            assert health.status == 200
            login_page = await client.get("/account/login")
            assert login_page.status == 200
            devices = await client.get("/v1/devices")
            assert devices.status == 200
            assert len((await devices.json())["devices"]) == 4

    asyncio.run(run())
