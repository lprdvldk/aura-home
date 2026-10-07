from __future__ import annotations

import json
from pathlib import Path

from smarthouse_hub.models import Device, DeviceKind, HouseConfig, Threshold


def load_house_config(path: Path) -> HouseConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    thresholds = {
        name: Threshold(low=float(bounds["low"]), high=float(bounds["high"]))
        for name, bounds in raw.get("thresholds", {}).items()
    }
    devices = [
        Device(
            id=item["id"],
            name=item["name"],
            room=item["room"],
            kind=DeviceKind(item["kind"]),
            driver=item.get("driver", "simulator"),
            gpio_pin=int(item.get("gpio_pin", 0)),
            enabled=bool(item.get("enabled", True)),
        )
        for item in raw.get("devices", [])
    ]
    return HouseConfig(
        house_name=str(raw.get("house_name", "Home")),
        sample_interval_ms=int(raw.get("sample_interval_ms", 1000)),
        agent_timeout_ms=int(raw.get("agent_timeout_ms", 5000)),
        history_points=int(raw.get("history_points", 360)),
        thresholds=thresholds,
        devices=devices,
    )


def default_config_path() -> Path:
    candidates = [
        Path(__file__).resolve().parents[3] / "config" / "house.json",
        Path.cwd() / "config" / "house.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]
