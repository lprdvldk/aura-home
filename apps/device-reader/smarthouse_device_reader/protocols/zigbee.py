import json
from pathlib import Path
from urllib.parse import urlparse

from smarthouse_hub.models import Metric, SensorSample
from smarthouse_hub.simulators import simulate_sample

from smarthouse_device_reader.protocol import DeviceBinding, DeviceProtocol, WriteCommand


class ZigbeeProtocol(DeviceProtocol):
    """Zigbee coordinator.

    Endpoints:
      sim://name          — local simulation (default for laptop / CI)
      file:///path.json   — last report dumped by zigbee2mqtt or a test fixture
      mqtt://host/topic   — reserved; returns a clear error until a broker is wired
    """

    name = "zigbee"

    def __init__(self) -> None:
        self.last_write: dict[str, WriteCommand] = {}

    def read(self, device: DeviceBinding, unix_ms: int) -> SensorSample:
        endpoint = device.endpoint or "sim://default"
        parsed = urlparse(endpoint)
        if parsed.scheme in {"sim", "simulator", ""}:
            sample = simulate_sample(device.as_hub_device(), unix_ms)
            sample.source = "agent"
            return sample
        if parsed.scheme == "file":
            return self._from_file(device, unix_ms, parsed.path)
        return SensorSample(
            device_id=device.id,
            unix_ms=unix_ms,
            metrics=[],
            error_code=4,
            error_message=f"zigbee endpoint not implemented: {endpoint}",
            source="agent",
        )

    def write(self, device: DeviceBinding, command: WriteCommand) -> None:
        self.last_write[device.id] = command

    def _from_file(self, device: DeviceBinding, unix_ms: int, path: str) -> SensorSample:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "metrics" in payload:
            return SensorSample.from_json({"device_id": device.id, "unix_ms": unix_ms, **payload, "source": "agent"})
        metrics = [Metric(str(k), float(v), "") for k, v in payload.items() if isinstance(v, (int, float))]
        return SensorSample(device.id, unix_ms, metrics, source="agent")
