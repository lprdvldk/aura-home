import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

import grpc

from smarthouse_hub.config import load_house_config, locate_house_config
from smarthouse_hub.generated.smarthouse.v1 import house_pb2, house_pb2_grpc
from smarthouse_hub.models import Device
from smarthouse_sensor_agent.readers import read_sample, to_proto


def _now_ms() -> int:
    return int(time.time() * 1000)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Push every house.json device into the hub over gRPC PushSamples"
    )
    parser.add_argument("--target", default=os.environ.get("SMART_HOUSE_GRPC_TARGET", "127.0.0.1:18551"))
    parser.add_argument("--config", default=os.environ.get("SMART_HOUSE_HOUSE_CONFIG", "config/house.json"))
    parser.add_argument(
        "--token",
        default=os.environ.get("SMART_HOUSE_AGENT_TOKEN", ""),
        help="Agent ingest token (x-agent-token). Defaults to SMART_HOUSE_AGENT_TOKEN.",
    )
    parser.add_argument(
        "--tls-ca",
        default=os.environ.get("SMART_HOUSE_TLS_CA", ""),
        help="PEM of the hub TLS certificate (self-signed CA) for encrypted gRPC.",
    )
    parser.add_argument(
        "--device",
        action="append",
        dest="devices",
        help="Limit to this device id (repeatable). Default: every enabled device.",
    )
    parser.add_argument(
        "--kind",
        action="append",
        dest="kinds",
        help="Limit to this kind (climate, air_quality, light, motion). Repeatable.",
    )
    parser.add_argument("--interval-ms", type=int, default=0)
    return parser.parse_args()


def select_devices(devices: list[Device], ids: list[str] | None, kinds: list[str] | None) -> list[Device]:
    chosen = [d for d in devices if d.enabled]
    if ids:
        wanted = set(ids)
        chosen = [d for d in chosen if d.id in wanted]
        missing = wanted - {d.id for d in chosen}
        if missing:
            print(f"unknown or disabled device ids: {', '.join(sorted(missing))}", file=sys.stderr)
    if kinds:
        wanted_kinds = {k.lower() for k in kinds}
        chosen = [d for d in chosen if d.kind.value in wanted_kinds]
    return chosen


def _channel(target: str, tls_ca: str):
    if tls_ca:
        pem = Path(tls_ca).read_bytes()
        creds = grpc.ssl_channel_credentials(root_certificates=pem)
        return grpc.aio.secure_channel(target, creds)
    return grpc.aio.insecure_channel(target)


async def push_loop(args: argparse.Namespace) -> None:
    config_path = locate_house_config(Path(args.config))
    house = load_house_config(config_path)
    devices = select_devices(house.devices, args.devices, args.kinds)
    if not devices:
        raise SystemExit("no enabled devices to push; check --device / --kind / house.json")
    interval = (args.interval_ms or house.sample_interval_ms) / 1000.0
    token = args.token.strip()
    metadata = (("x-agent-token", token),) if token else ()
    print(f"sensor-agent  {len(devices)} device(s) -> gRPC {args.target}")
    for device in devices:
        print(f"  {device.id:24}  {device.kind.value:12}  driver={device.driver}")
    if not token:
        print("warning: no agent token; hub will reject ingest if SMART_HOUSE_REQUIRE_AGENT_TOKEN=true")
    if args.tls_ca:
        print(f"  TLS CA         {args.tls_ca}")

    while True:
        try:
            async with _channel(args.target, args.tls_ca) as channel:
                stub = house_pb2_grpc.HouseHubStub(channel)
                while True:
                    unix_ms = _now_ms()
                    samples = [to_proto(read_sample(device, unix_ms), house_pb2) for device in devices]
                    response = await stub.PushSamples(
                        house_pb2.PushSamplesRequest(samples=samples),
                        metadata=metadata,
                        timeout=5.0,
                    )
                    print(
                        f"pushed {response.accepted} accepted, {response.rejected} rejected",
                        flush=True,
                    )
                    await asyncio.sleep(max(0.2, interval))
        except grpc.aio.AioRpcError as exc:
            print(f"gRPC push failed: {exc.code().name} {exc.details()}", file=sys.stderr)
            await asyncio.sleep(2.0)
        except OSError as exc:
            print(f"gRPC connect failed: {exc}", file=sys.stderr)
            await asyncio.sleep(2.0)


def main() -> None:
    try:
        asyncio.run(push_loop(parse_args()))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
