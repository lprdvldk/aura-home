from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import grpc
from aiohttp import web

ROOT = Path(__file__).resolve().parents[3]
HUB_DIR = Path(__file__).resolve().parents[1]
if str(HUB_DIR) not in sys.path:
    sys.path.insert(0, str(HUB_DIR))

from smarthouse_hub.config import default_config_path, load_house_config
from smarthouse_hub.grpc_servicer import HouseHubServicer
from smarthouse_hub.http_app import create_http_app
from smarthouse_hub.store import HouseStore
from smarthouse_hub.generated.smarthouse.v1 import house_pb2_grpc


async def simulator_loop(store: HouseStore) -> None:
    interval = max(0.2, store.config.sample_interval_ms / 1000.0)
    while True:
        await store.tick_simulators()
        await asyncio.sleep(interval)


async def run(config_path: Path, http_host: str, http_port: int, grpc_port: int) -> None:
    config = load_house_config(config_path)
    store = HouseStore(config)
    http_app = create_http_app(store)
    runner = web.AppRunner(http_app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, http_host, http_port)
    await site.start()

    server = grpc.aio.server()
    house_pb2_grpc.add_HouseHubServicer_to_server(HouseHubServicer(store), server)
    bind = f"{http_host}:{grpc_port}"
    bound = server.add_insecure_port(bind)
    if bound == 0:
        raise RuntimeError(f"could not bind gRPC on {bind}")
    await server.start()

    print(f"Smart House hub  '{config.house_name}'")
    print(f"  HTTP/WebSocket  http://{http_host}:{http_port}/")
    print(f"  Telemetry WS    ws://{http_host}:{http_port}/v1/telemetry")
    print(f"  gRPC            {http_host}:{grpc_port}")
    print(f"  Devices         {len(config.devices)}")

    stop = asyncio.Event()
    sim_task = asyncio.create_task(simulator_loop(store))
    try:
        await stop.wait()
    except asyncio.CancelledError:
        pass
    finally:
        sim_task.cancel()
        await server.stop(grace=0.5)
        await runner.cleanup()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smart House local hub")
    parser.add_argument("--config", type=Path, default=default_config_path())
    parser.add_argument("--http-host", default=os.environ.get("SMART_HOUSE_HTTP_HOST", "0.0.0.0"))
    parser.add_argument("--http-port", type=int, default=int(os.environ.get("SMART_HOUSE_HTTP_PORT", "18443")))
    parser.add_argument("--grpc-port", type=int, default=int(os.environ.get("SMART_HOUSE_GRPC_PORT", "18551")))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(run(args.config, args.http_host, args.http_port, args.grpc_port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
