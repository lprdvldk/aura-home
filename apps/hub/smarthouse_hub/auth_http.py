from __future__ import annotations

from pathlib import Path

from aiohttp import web

from smarthouse_hub.crypto_vault import AuthError, UserVault

PAGES = Path(__file__).with_name("pages")
COOKIE = "sh_session"
VAULT_KEY = web.AppKey("vault", UserVault)


async def login_page(_request: web.Request) -> web.StreamResponse:
    return web.FileResponse(PAGES / "login.html")


async def register_page(_request: web.Request) -> web.StreamResponse:
    return web.FileResponse(PAGES / "register.html")


async def bio_page(_request: web.Request) -> web.StreamResponse:
    return web.FileResponse(PAGES / "bio.html")


def setup_auth(app: web.Application, vault: UserVault) -> None:
    app[VAULT_KEY] = vault
    app.router.add_get("/account/login", login_page)
    app.router.add_get("/account/register", register_page)
    app.router.add_get("/account/bio", bio_page)
    app.router.add_post("/v1/auth/register", register)
    app.router.add_post("/v1/auth/login", login)
    app.router.add_post("/v1/auth/logout", logout)
    app.router.add_get("/v1/auth/me", me)
    app.router.add_get("/v1/bio", get_bio)
    app.router.add_put("/v1/bio", put_bio)


def _token(request: web.Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()
    return request.cookies.get(COOKIE)


def _ok(payload: dict, token: str | None = None) -> web.Response:
    response = web.json_response(payload)
    if token:
        response.set_cookie(COOKIE, token, httponly=True, samesite="Lax", path="/", max_age=12 * 3600)
    return response


def _clear(payload: dict) -> web.Response:
    response = web.json_response(payload)
    response.del_cookie(COOKIE, path="/")
    return response


def _fail(exc: AuthError) -> web.Response:
    return web.json_response({"error": exc.message}, status=exc.status)


async def register(request: web.Request) -> web.Response:
    vault: UserVault = request.app[VAULT_KEY]
    body = await request.json()
    try:
        result = await vault.register(str(body.get("username", "")), str(body.get("password", "")), body.get("profile"))
    except AuthError as exc:
        return _fail(exc)
    return _ok({"ok": True, "username": result["username"]}, result["token"])


async def login(request: web.Request) -> web.Response:
    vault: UserVault = request.app[VAULT_KEY]
    body = await request.json()
    try:
        result = await vault.login(str(body.get("username", "")), str(body.get("password", "")))
    except AuthError as exc:
        return _fail(exc)
    return _ok({"ok": True, "username": result["username"]}, result["token"])


async def logout(request: web.Request) -> web.Response:
    vault: UserVault = request.app[VAULT_KEY]
    await vault.logout(_token(request))
    return _clear({"ok": True})


async def me(request: web.Request) -> web.Response:
    vault: UserVault = request.app[VAULT_KEY]
    try:
        session = vault.session(_token(request))
    except AuthError as exc:
        return _fail(exc)
    return web.json_response({"ok": True, "username": session.username})


async def get_bio(request: web.Request) -> web.Response:
    vault: UserVault = request.app[VAULT_KEY]
    try:
        return web.json_response(await vault.get_bio(_token(request)))
    except AuthError as exc:
        return _fail(exc)


async def put_bio(request: web.Request) -> web.Response:
    vault: UserVault = request.app[VAULT_KEY]
    body = await request.json()
    try:
        return web.json_response(await vault.put_bio(_token(request), body.get("profile", body)))
    except AuthError as exc:
        return _fail(exc)
