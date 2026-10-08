import asyncio
import time
from collections import deque
from typing import Any

from smarthouse_hub.models import (
    Alert,
    Device,
    DeviceStatus,
    HouseConfig,
    SensorSample,
)
from smarthouse_hub.simulators import simulate_sample


def now_ms() -> int:
    return int(time.time() * 1000)


class HouseStore:
    def __init__(self, config: HouseConfig) -> None:
        self.config = config
        self.devices: dict[str, Device] = {d.id: d for d in config.devices}
        self.latest: dict[str, SensorSample] = {}
        self.history: dict[str, deque[SensorSample]] = {
            device_id: deque(maxlen=config.history_points) for device_id in self.devices
        }
        self.alerts: deque[Alert] = deque(maxlen=40)
        self._subscribers: set[asyncio.Queue] = set()
        self._agent_devices: set[str] = set()
        self._lock = asyncio.Lock()

    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def snapshot(self) -> dict[str, Any]:
        return {
            "house_name": self.config.house_name,
            "devices": [d.to_json() for d in self.devices.values()],
            "latest": {did: sample.to_json() for did, sample in self.latest.items()},
            "alerts": [a.to_json() for a in self.alerts],
        }

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=32)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    async def set_enabled(self, device_id: str, enabled: bool) -> Device:
        async with self._lock:
            device = self.devices[device_id]
            device.enabled = enabled
            if not enabled:
                device.status = DeviceStatus.DISABLED
            elif device_id in self._agent_devices:
                device.status = DeviceStatus.ONLINE
            else:
                device.status = DeviceStatus.SIMULATED
            return device

    async def push_sample(self, sample: SensorSample, *, from_agent: bool) -> bool:
        async with self._lock:
            device = self.devices.get(sample.device_id)
            if device is None or not device.enabled:
                return False
            if sample.unix_ms <= 0:
                sample.unix_ms = now_ms()
            if from_agent:
                sample.source = sample.source or "agent"
                self._agent_devices.add(device.id)
                device.last_seen_ms = sample.unix_ms
                device.status = DeviceStatus.ERROR if sample.error_code else DeviceStatus.ONLINE
            else:
                sample.source = "simulator"
                if device.id not in self._agent_devices:
                    device.status = DeviceStatus.SIMULATED
            self.latest[device.id] = sample
            self.history[device.id].append(sample)
            alerts = self._evaluate_alerts(device, sample)
            event = {"type": "sample", "sample": sample.to_json(), "device": device.to_json()}
        for alert in alerts:
            await self._broadcast({"type": "alert", "alert": alert.to_json()})
        await self._broadcast(event)
        return True

    def history_json(self, device_id: str, limit: int = 180) -> list[dict[str, Any]]:
        points = list(self.history.get(device_id, ()))
        if limit > 0:
            points = points[-limit:]
        return [p.to_json() for p in points]

    async def tick_simulators(self) -> None:
        ts = now_ms()
        timeout = self.config.agent_timeout_ms
        async with self._lock:
            expired = [
                device_id
                for device_id in list(self._agent_devices)
                if ts - self.devices[device_id].last_seen_ms > timeout
            ]
            for device_id in expired:
                self._agent_devices.discard(device_id)
                device = self.devices[device_id]
                if device.enabled:
                    device.status = DeviceStatus.SIMULATED
            to_simulate = [
                device
                for device in self.devices.values()
                if device.enabled and device.id not in self._agent_devices
            ]
        for device in to_simulate:
            sample = simulate_sample(device, ts)
            await self.push_sample(sample, from_agent=False)

    def _evaluate_alerts(self, device: Device, sample: SensorSample) -> list[Alert]:
        issued: list[Alert] = []
        values = sample.metric_map()
        for name, threshold in self.config.thresholds.items():
            if name not in values:
                continue
            value = values[name]
            if value > threshold.high:
                message = f"{device.name}: {name} is {value:g}, above {threshold.high:g}"
                severity = "warning"
            elif value < threshold.low:
                message = f"{device.name}: {name} is {value:g}, below {threshold.low:g}"
                severity = "info"
            else:
                continue
            alert = Alert(
                id=f"{device.id}:{name}:{sample.unix_ms}",
                device_id=device.id,
                metric=name,
                message=message,
                severity=severity,
                unix_ms=sample.unix_ms,
            )
            self.alerts.appendleft(alert)
            issued.append(alert)
        return issued

    async def _broadcast(self, event: dict[str, Any]) -> None:
        stale: list[asyncio.Queue[Any]] = []
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                stale.append(queue)
        for queue in stale:
            self.unsubscribe(queue)
