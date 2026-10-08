import argparse
import asyncio

import grpc
import uvicorn

from smarthouse_hub.app import create_app
from smarthouse_hub.config import load_house_config, locate_house_config
from smarthouse_hub.crypto_vault import UserVault
from smarthouse_hub.generated.smarthouse.v1 import house_pb2_grpc
from smarthouse_hub.grpc_servicer import HouseHubServicer
from smarthouse_hub.settings import Settings, load_settings
from smarthouse_hub.store import HouseStore


async def simulator_loop(store: HouseStore) -> None:
    interval = max(0.2, store.config.sample_interval_ms / 1000.0)
    while True:
        await store.tick_simulators()
        await asyncio.sleep(interval)


async def serve(settings: Settings) -> None:
    config_path = locate_house_config(settings.house_config)
    store = HouseStore(load_house_config(config_path))
    vault = UserVault(settings.data_dir)
    app = create_app(store, vault, settings)

    grpc_server = grpc.aio.server()
    house_pb2_grpc.add_HouseHubServicer_to_server(HouseHubServicer(store), grpc_server)
    bind = f"{settings.grpc_host}:{settings.grpc_port}"
    if grpc_server.add_insecure_port(bind) == 0:
        raise RuntimeError(f"could not bind gRPC on {bind}")
    await grpc_server.start()

    print(f"Smart House hub  '{store.config.house_name}'")
    print(f"  config          {config_path}")
    print(f"  HTTP/WebSocket  http://{settings.http_host}:{settings.http_port}/")
    print(f"  Account         http://{settings.http_host}:{settings.http_port}/account/login")
    print(f"  Telemetry WS    ws://{settings.http_host}:{settings.http_port}/v1/telemetry")
    print(f"  gRPC            {bind}")
    print(f"  Devices         {len(store.config.devices)}")

    sim_task = asyncio.create_task(simulator_loop(store))
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=settings.http_host,
            port=settings.http_port,
            loop="asyncio",
            log_level="warning",
        )
    )
    try:
        await server.serve()
    finally:
        sim_task.cancel()
        await grpc_server.stop(grace=0.5)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smart House local hub")
    parser.add_argument("--http-host")
    parser.add_argument("--http-port", type=int)
    parser.add_argument("--grpc-host")
    parser.add_argument("--grpc-port", type=int)
    parser.add_argument("--config")
    parser.add_argument("--data-dir")
    return parser.parse_args()


def settings_from_args() -> Settings:
    settings = load_settings()
    args = parse_args()
    updates = {}
    if args.http_host:
        updates["http_host"] = args.http_host
    if args.http_port is not None:
        updates["http_port"] = args.http_port
    if args.grpc_host:
        updates["grpc_host"] = args.grpc_host
    if args.grpc_port is not None:
        updates["grpc_port"] = args.grpc_port
    if args.config:
        updates["house_config"] = args.config
    if args.data_dir:
        updates["data_dir"] = args.data_dir
    if updates:
        settings = settings.model_copy(update=updates)
    return settings


def main() -> None:
    try:
        asyncio.run(serve(settings_from_args()))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
