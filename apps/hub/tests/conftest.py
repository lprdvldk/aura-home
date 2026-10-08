from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from smarthouse_hub.app import create_app
from smarthouse_hub.config import load_house_config, locate_house_config
from smarthouse_hub.crypto_vault import UserVault
from smarthouse_hub.settings import Settings
from smarthouse_hub.store import HouseStore


@pytest.fixture
def house_config_path() -> Path:
    return locate_house_config(Path("config/house.json"))


@pytest.fixture
def client(tmp_path: Path, house_config_path: Path) -> TestClient:
    settings = Settings(house_config=house_config_path, data_dir=tmp_path)
    store = HouseStore(load_house_config(house_config_path))
    app = create_app(store, UserVault(tmp_path), settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def store(house_config_path: Path) -> HouseStore:
    return HouseStore(load_house_config(house_config_path))
