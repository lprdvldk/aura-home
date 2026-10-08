import asyncio
import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from smarthouse_hub.auth_http import auth_router
from smarthouse_hub.crypto_vault import UserVault
from smarthouse_hub.models import SensorSample
from smarthouse_hub.security import agent_allowed, token_from_request
from smarthouse_hub.settings import Settings
from smarthouse_hub.store import HouseStore


def package_path(*parts: str) -> Path:
    return Path(str(files("smarthouse_hub").joinpath(*parts)))


def create_app(store: HouseStore, vault: UserVault, settings: Settings) -> FastAPI:
    app = FastAPI(title="Aura Home Hub", version="0.2.0")
    app.state.store = store
    app.state.vault = vault
    app.state.settings = settings

    origins = settings.cors_origin_list()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=origins != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    static_dir = package_path("static")
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    app.include_router(auth_router)

    @app.get("/")
    async def dashboard() -> FileResponse:
        return FileResponse(package_path("dashboard.html"))

    @app.get("/favicon.ico")
    async def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "house": store.config.house_name,
            "devices": len(store.devices),
            "subscribers": store.subscriber_count(),
        }

    @app.get("/v1/snapshot")
    async def snapshot() -> dict[str, Any]:
        return store.snapshot()

    @app.get("/v1/devices")
    async def list_devices() -> dict[str, Any]:
        return {"devices": [device.to_json() for device in store.devices.values()]}

    @app.get("/v1/devices/{device_id}/latest")
    async def latest(device_id: str) -> dict[str, Any]:
        sample = store.latest.get(device_id)
        if sample is None:
            raise HTTPException(status_code=404, detail="no sample yet")
        return sample.to_json()

    @app.get("/v1/devices/{device_id}/history")
    async def history(device_id: str, limit: int = 180) -> dict[str, Any]:
        if device_id not in store.devices:
            raise HTTPException(status_code=404, detail="unknown device")
        return {"points": store.history_json(device_id, limit)}

    @app.post("/v1/devices/{device_id}/enabled")
    async def set_enabled(device_id: str, body: dict[str, Any]) -> dict[str, Any]:
        if device_id not in store.devices:
            raise HTTPException(status_code=404, detail="unknown device")
        device = await store.set_enabled(device_id, bool(body.get("enabled", True)))
        return device.to_json()

    @app.post("/v1/samples")
    async def push_sample(request: Request, body: dict[str, Any]) -> dict[str, Any]:
        if not agent_allowed(settings, token_from_request(request)):
            raise HTTPException(status_code=401, detail="invalid agent token")
        sample = SensorSample.from_json(body)
        accepted = await store.push_sample(sample, from_agent=True)
        if not accepted:
            raise HTTPException(status_code=400, detail="device missing or disabled")
        return {"accepted": True}

    @app.websocket("/v1/telemetry")
    async def telemetry(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_json({"type": "snapshot", **store.snapshot()})
        queue = store.subscribe()

        async def pump() -> None:
            while True:
                event = await queue.get()
                await websocket.send_text(json.dumps(event))

        sender = asyncio.create_task(pump())
        try:
            while True:
                message = await websocket.receive_text()
                if message == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            pass
        finally:
            sender.cancel()
            store.unsubscribe(queue)

    return app
