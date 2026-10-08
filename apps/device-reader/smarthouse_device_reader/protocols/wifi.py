import json
import urllib.error
import urllib.request
from urllib.parse import urlparse

from smarthouse_hub.models import Metric, SensorSample
from smarthouse_hub.simulators import simulate_sample

from smarthouse_device_reader.protocol import DeviceBinding, DeviceProtocol, WriteCommand


class WifiProtocol(DeviceProtocol):
    """HTTP gadgets (ESPHome, a Wi-Fi DHT module, etc.).

    sim://name — simulation. http(s)://host/path — GET JSON metrics; write POSTs the command.
    """

    name = "wifi"

    def __init__(self, timeout_s: float = 2.0) -> None:
        self.timeout_s = timeout_s
        self.last_write: dict[str, WriteCommand] = {}

    def read(self, device: DeviceBinding, unix_ms: int) -> SensorSample:
        endpoint = device.endpoint or "sim://default"
        parsed = urlparse(endpoint)
        if parsed.scheme in {"sim", "simulator", ""}:
            sample = simulate_sample(device.as_hub_device(), unix_ms)
            sample.source = "agent"
            return sample
        if parsed.scheme not in {"http", "https"}:
            return SensorSample(
                device_id=device.id,
                unix_ms=unix_ms,
                metrics=[],
                error_code=4,
                error_message=f"wifi endpoint must be http(s) or sim:// ({endpoint})",
                source="agent",
            )
        try:
            with urllib.request.urlopen(endpoint, timeout=self.timeout_s) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            return SensorSample(
                device_id=device.id,
                unix_ms=unix_ms,
                metrics=[],
                error_code=4,
                error_message=str(exc),
                source="agent",
            )
        if isinstance(payload, dict) and "metrics" in payload:
            data = dict(payload)
            data["device_id"] = device.id
            data["unix_ms"] = unix_ms
            data["source"] = "agent"
            return SensorSample.from_json(data)
        metrics = [
            Metric(str(key), float(value), "")
            for key, value in payload.items()
            if isinstance(value, (int, float))
        ]
        return SensorSample(device.id, unix_ms, metrics, source="agent")

    def write(self, device: DeviceBinding, command: WriteCommand) -> None:
        self.last_write[device.id] = command
        endpoint = device.endpoint or ""
        parsed = urlparse(endpoint)
        if parsed.scheme not in {"http", "https"}:
            return
        body = json.dumps({"action": command.action, "enabled": command.enabled, **command.extra}).encode("utf-8")
        request = urllib.request.Request(endpoint, data=body, method="POST")
        request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
            response.read()
