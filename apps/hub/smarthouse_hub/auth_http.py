from importlib.resources import files
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

from smarthouse_hub.crypto_vault import AuthError, UserVault

auth_router = APIRouter()
COOKIE = "sh_session"


def _pages(*parts: str) -> Path:
    return Path(str(files("smarthouse_hub").joinpath("pages", *parts)))


def _vault(request: Request) -> UserVault:
    return request.app.state.vault


def _token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.cookies.get(COOKIE)


def _session_cookie(request: Request, payload: dict[str, Any], token: str) -> JSONResponse:
    hours = int(request.app.state.settings.session_hours)
    response = JSONResponse(payload)
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=hours * 3600,
    )
    return response


def _fail(exc: AuthError) -> JSONResponse:
    return JSONResponse({"error": exc.message}, status_code=exc.status)


@auth_router.get("/account/login")
async def login_page() -> FileResponse:
    return FileResponse(_pages("login.html"))


@auth_router.get("/account/register")
async def register_page() -> FileResponse:
    return FileResponse(_pages("register.html"))


@auth_router.get("/account/bio")
async def bio_page() -> FileResponse:
    return FileResponse(_pages("bio.html"))


@auth_router.post("/v1/auth/register")
async def register(request: Request, body: dict[str, Any]) -> JSONResponse:
    try:
        result = await _vault(request).register(
            str(body.get("username", "")),
            str(body.get("password", "")),
            body.get("profile"),
        )
    except AuthError as exc:
        return _fail(exc)
    return _session_cookie(request, {"ok": True, "username": result["username"]}, result["token"])


@auth_router.post("/v1/auth/login")
async def login(request: Request, body: dict[str, Any]) -> JSONResponse:
    try:
        result = await _vault(request).login(str(body.get("username", "")), str(body.get("password", "")))
    except AuthError as exc:
        return _fail(exc)
    return _session_cookie(request, {"ok": True, "username": result["username"]}, result["token"])


@auth_router.post("/v1/auth/logout")
async def logout(request: Request) -> JSONResponse:
    await _vault(request).logout(_token(request))
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE, path="/")
    return response


@auth_router.get("/v1/auth/me")
async def me(request: Request) -> JSONResponse:
    try:
        session = _vault(request).session(_token(request))
    except AuthError as exc:
        return _fail(exc)
    return JSONResponse({"ok": True, "username": session.username})


@auth_router.get("/v1/bio")
async def get_bio(request: Request) -> JSONResponse:
    try:
        return JSONResponse(await _vault(request).get_bio(_token(request)))
    except AuthError as exc:
        return _fail(exc)


@auth_router.put("/v1/bio")
async def put_bio(request: Request, body: dict[str, Any]) -> JSONResponse:
    try:
        return JSONResponse(await _vault(request).put_bio(_token(request), body.get("profile", body)))
    except AuthError as exc:
        return _fail(exc)
