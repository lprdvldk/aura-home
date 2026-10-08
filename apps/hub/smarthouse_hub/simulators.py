import math
import random

from smarthouse_hub.models import Device, DeviceKind, Metric, SensorSample


def _quantize_dht11(temperature_c: float, humidity_pct: float) -> tuple[float, float]:
    """DHT11 reports whole degrees and whole percent RH."""
    return float(round(temperature_c)), float(round(humidity_pct))


def simulate_sample(device: Device, unix_ms: int) -> SensorSample:
    t = unix_ms / 1000.0
    if device.kind == DeviceKind.CLIMATE:
        temperature = 21.4 + 2.2 * math.sin(t / 180.0) + random.uniform(-0.15, 0.15)
        humidity = 46.0 + 7.5 * math.sin(t / 240.0 + 0.8) + random.uniform(-0.25, 0.25)
        if device.room.lower().startswith("bed"):
            temperature -= 1.2
            humidity += 3.0
        temperature, humidity = _quantize_dht11(temperature, humidity)
        metrics = [
            Metric("temperature_c", temperature, "°C"),
            Metric("humidity_pct", humidity, "%"),
        ]
        driver_source = "simulator"
        return SensorSample(device.id, unix_ms, metrics, source=driver_source)

    if device.kind == DeviceKind.AIR_QUALITY:
        pm25 = max(4.0, 12.0 + 6.0 * math.sin(t / 150.0) + random.uniform(-1.2, 1.2))
        voc = max(50.0, 110.0 + 25.0 * math.sin(t / 200.0 + 1.1) + random.uniform(-4, 4))
        co2 = 640.0 + 90.0 * math.sin(t / 260.0) + random.uniform(-12, 12)
        if device.room.lower().startswith("kit"):
            pm25 += 8.0
            voc += 20.0
            co2 += 80.0
        metrics = [
            Metric("pm25_ugm3", round(pm25, 1), "µg/m³"),
            Metric("voc_index", round(voc, 1), "index"),
            Metric("co2_ppm", round(co2), "ppm"),
        ]
        return SensorSample(device.id, unix_ms, metrics, source="simulator")

    if device.kind == DeviceKind.LIGHT:
        lux = max(0.0, 180.0 + 120.0 * math.sin(t / 90.0) + random.uniform(-8, 8))
        return SensorSample(
            device.id,
            unix_ms,
            [Metric("lux", round(lux, 1), "lx")],
            source="simulator",
        )

    moving = 1.0 if (int(t) // 17) % 9 == 0 else 0.0
    return SensorSample(
        device.id,
        unix_ms,
        [Metric("motion", moving, "bool")],
        source="simulator",
    )
