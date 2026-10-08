from fastapi.testclient import TestClient

from smarthouse_hub.app import create_app
from smarthouse_hub.config import load_house_config
from smarthouse_hub.crypto_vault import UserVault
from smarthouse_hub.main import _pin_secrets
from smarthouse_hub.settings import Settings
from smarthouse_hub.store import HouseStore
import pytest


def test_cloud_mode_requires_tls() -> None:
    with pytest.raises(RuntimeError, match="TLS"):
        _pin_secrets(Settings(cloud_mode=True, agent_token="a", viewer_token="v"))


def test_snapshot_requires_viewer_token(tmp_path, house_config_path) -> None:
    settings = Settings(
        house_config=house_config_path,
        data_dir=tmp_path,
        agent_token="agent-secret",
        viewer_token="viewer-secret",
        require_agent_token=True,
        require_viewer_token=True,
    )
    app = create_app(HouseStore(load_house_config(house_config_path)), UserVault(tmp_path), settings)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/v1/snapshot").status_code == 401
        assert client.get("/v1/devices").status_code == 401
        ok = client.get("/v1/snapshot", headers={"X-Viewer-Token": "viewer-secret"})
        assert ok.status_code == 200
        via_query = client.get("/v1/snapshot?token=viewer-secret")
        assert via_query.status_code == 200
        via_agent = client.get("/v1/snapshot", headers={"X-Agent-Token": "agent-secret"})
        assert via_agent.status_code == 200


def test_session_unlocks_viewer_routes(tmp_path, house_config_path) -> None:
    settings = Settings(
        house_config=house_config_path,
        data_dir=tmp_path,
        agent_token="agent-secret",
        viewer_token="viewer-secret",
        require_agent_token=True,
        require_viewer_token=True,
    )
    app = create_app(HouseStore(load_house_config(house_config_path)), UserVault(tmp_path), settings)
    with TestClient(app) as client:
        created = client.post(
            "/v1/auth/register",
            json={"username": "pi_owner", "password": "correct-horse-battery", "profile": {}},
        )
        assert created.status_code == 200
        snap = client.get("/v1/snapshot")
        assert snap.status_code == 200
