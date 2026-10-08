import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

import grpc

from smarthouse_hub.config import load_house_config, locate_house_config
from smarthouse_hub.generated.smarthouse.v1 import house_pb2, house_pb2_grpc

from smarthouse_device_reader.builder import DeviceReaderBuilder
from smarthouse_device_reader.protocol import WriteCommand
from smarthouse_device_reader.protocols import GpioProtocol, SimulatorProtocol, WifiProtocol, ZigbeeProtocol


def _now_ms() -> int:
    return int(time.time() * 1000)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="device-reader: GPIO / Zigbee / Wi-Fi / simulator → hub gRPC PushSamples"
    )
    parser.add_argument("--target", default=os.environ.get("SMART_HOUSE_GRPC_TARGET", "127.0.0.1:18551"))
    parser.add_argument("--config", default=os.environ.get("SMART_HOUSE_HOUSE_CONFIG", "config/house.json"))
    parser.add_argument("--token", default=os.environ.get("SMART_HOUSE_AGENT_TOKEN", ""))
    parser.add_argument("--tls-ca", default=os.environ.get("SMART_HOUSE_TLS_CA", ""))
    parser.add_argument("--device", action="append", dest="devices")
    parser.add_argument("--kind", action="append", dest="kinds")
    parser.add_argument("--protocol", action="append", dest="protocols")
    parser.add_argument("--gpio", action="store_true", help="Use C++ GPIO oneshot for protocol=gpio")
    parser.add_argument("--interval-ms", type=int, default=0)
    return parser.parse_args()


def _channel(target: str, tls_ca: str):
    if tls_ca:
        pem = Path(tls_ca).read_bytes()
        creds = grpc.ssl_channel_credentials(root_certificates=pem)
        return grpc.aio.secure_channel(target, creds)
    return grpc.aio.insecure_channel(target)


def build_reader(args: argparse.Namespace):
    builder = (
        DeviceReaderBuilder()
        .protocol(SimulatorProtocol())
        .protocol(GpioProtocol(hardware=args.gpio))
        .protocol(ZigbeeProtocol())
        .protocol(WifiProtocol())
        .devices_from_house(args.config)
        .hub(args.target, token=args.token, tls_ca=args.tls_ca)
    )
    reader = builder.build()
    devices = reader.devices
    if args.devices:
        wanted = set(args.devices)
        devices = [d for d in devices if d.id in wanted]
    if args.kinds:
        kinds = {k.lower() for k in args.kinds}
        devices = [d for d in devices if d.kind in kinds]
    if args.protocols:
        names = {p.lower() for p in args.protocols}
        devices = [d for d in devices if d.protocol in names]
    reader._devices = {d.id: d for d in devices}  # noqa: SLF001 — filter after build
    if not reader.devices:
        raise SystemExit("no enabled devices to read; check --device / --kind / --protocol / house.json")
    return reader, builder


async def push_loop(args: argparse.Namespace) -> None:
    house = load_house_config(locate_house_config(Path(args.config)))
    reader, builder = build_reader(args)
    interval = (args.interval_ms or house.sample_interval_ms) / 1000.0
    token = (builder.hub_token or args.token).strip()
    metadata = (("x-agent-token", token),) if token else ()
    print(f"device-reader  {len(reader.devices)} device(s) -> gRPC {args.target}")
    for device in reader.devices:
        print(
            f"  {device.id:24}  {device.kind:12}  protocol={device.protocol:9}  driver={device.driver}"
        )
    if not token:
        print("warning: no agent token; hub will reject ingest if SMART_HOUSE_REQUIRE_AGENT_TOKEN=true")
    if args.tls_ca:
        print(f"  TLS CA         {args.tls_ca}")
    if args.gpio:
        print("  GPIO           hardware oneshot (smarthouse_dht11_agent --once)")

    last_enabled: dict[str, bool] = {d.id: d.enabled for d in reader.devices}

    while True:
        try:
            async with _channel(args.target, args.tls_ca) as channel:
                stub = house_pb2_grpc.HouseHubStub(channel)
                while True:
                    listed = await stub.ListDevices(house_pb2.ListDevicesRequest(), metadata=metadata, timeout=5.0)
                    for proto_dev in listed.devices:
                        local = next((d for d in reader.devices if d.id == proto_dev.id), None)
                        if local is None:
                            continue
                        if last_enabled.get(local.id) != proto_dev.enabled:
                            try:
                                reader.write(local.id, WriteCommand(action="enable", enabled=proto_dev.enabled))
                            except NotImplementedError as exc:
                                print(f"write skipped {local.id}: {exc}", file=sys.stderr)
                            last_enabled[local.id] = proto_dev.enabled
                            local.enabled = proto_dev.enabled
                    unix_ms = _now_ms()
                    samples = reader.read(unix_ms=unix_ms)
                    response = await stub.PushSamples(
                        house_pb2.PushSamplesRequest(samples=reader.to_proto(samples)),
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
