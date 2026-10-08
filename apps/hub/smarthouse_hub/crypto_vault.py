import asyncio
import base64
import hashlib
import json
import os
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")
AAD = b"smarthouse-bio-v1"
PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=2, hash_len=32)
BIO_FIELDS = (
    "full_name",
    "email",
    "phone",
    "date_of_birth",
    "address",
    "city",
    "country",
    "emergency_contact",
    "household_role",
    "notes",
)


class AuthError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


@dataclass(slots=True)
class Session:
    token: str
    user_id: str
    username: str
    data_key: bytes
    expires_unix: int


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data.encode("ascii"))


def _now() -> int:
    return int(time.time())


def derive_data_key(password: str, salt: bytes) -> bytes:
    return hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        time_cost=3,
        memory_cost=64 * 1024,
        parallelism=2,
        hash_len=32,
        type=Type.ID,
    )


def encrypt_profile(data_key: bytes, profile: dict[str, str]) -> dict[str, str]:
    nonce = os.urandom(12)
    aes = AESGCM(data_key)
    plaintext = json.dumps(profile, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ciphertext = aes.encrypt(nonce, plaintext, AAD)
    return {
        "alg": "AES-256-GCM",
        "kdf": "argon2id",
        "aad": AAD.decode("ascii"),
        "nonce": _b64(nonce),
        "ciphertext": _b64(ciphertext),
    }


def decrypt_profile(data_key: bytes, blob: dict[str, str]) -> dict[str, str]:
    aes = AESGCM(data_key)
    plaintext = aes.decrypt(_unb64(blob["nonce"]), _unb64(blob["ciphertext"]), AAD)
    data = json.loads(plaintext.decode("utf-8"))
    return {field: str(data.get(field, "")) for field in BIO_FIELDS}


def sanitize_profile(raw: dict[str, Any] | None) -> dict[str, str]:
    raw = raw or {}
    profile: dict[str, str] = {}
    for field in BIO_FIELDS:
        value = str(raw.get(field, "")).strip()
        if len(value) > 400:
            raise AuthError(f"{field} is too long")
        profile[field] = value
    return profile


class UserVault:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else Path("data/users")
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._sessions: dict[str, Session] = {}

    def _user_path(self, username: str) -> Path:
        digest = hashlib.sha256(username.lower().encode("utf-8")).hexdigest()
        return self.root / f"{digest}.json"

    def _read_user(self, username: str) -> dict[str, Any] | None:
        path = self._user_path(username)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_user(self, record: dict[str, Any]) -> None:
        path = self._user_path(record["username"])
        tmp = path.with_suffix(".tmp")
        payload = json.dumps(record, indent=2, sort_keys=True)
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    async def register(self, username: str, password: str, profile: dict[str, Any] | None) -> dict[str, str]:
        username = username.strip()
        if not USERNAME_RE.match(username):
            raise AuthError("Username must be 3-32 letters, digits, or underscores")
        if len(password) < 10:
            raise AuthError("Password must be at least 10 characters")
        async with self._lock:
            if self._read_user(username) is not None:
                raise AuthError("That username is already registered", 409)
            salt = os.urandom(16)
            data_key = derive_data_key(password, salt)
            record = {
                "user_id": secrets.token_hex(16),
                "username": username,
                "password_hash": PASSWORD_HASHER.hash(password),
                "kdf_salt": _b64(salt),
                "profile_blob": encrypt_profile(data_key, sanitize_profile(profile)),
                "created_unix": _now(),
            }
            self._write_user(record)
            session = self._create_session(record["user_id"], username, data_key)
        return {"token": session.token, "username": username}

    async def login(self, username: str, password: str) -> dict[str, str]:
        username = username.strip()
        async with self._lock:
            record = self._read_user(username)
            if record is None:
                raise AuthError("Invalid username or password", 401)
            try:
                PASSWORD_HASHER.verify(record["password_hash"], password)
            except VerifyMismatchError as exc:
                raise AuthError("Invalid username or password", 401) from exc
            data_key = derive_data_key(password, _unb64(record["kdf_salt"]))
            decrypt_profile(data_key, record["profile_blob"])  # fail closed if the blob is corrupt
            session = self._create_session(record["user_id"], record["username"], data_key)
        return {"token": session.token, "username": record["username"]}

    async def logout(self, token: str | None) -> None:
        if not token:
            return
        async with self._lock:
            self._sessions.pop(token, None)

    def session(self, token: str | None) -> Session:
        if not token:
            raise AuthError("Sign in required", 401)
        session = self._sessions.get(token)
        if session is None or session.expires_unix < _now():
            self._sessions.pop(token or "", None)
            raise AuthError("Sign in required", 401)
        return session

    async def get_bio(self, token: str | None) -> dict[str, Any]:
        session = self.session(token)
        async with self._lock:
            record = self._read_user(session.username)
            if record is None:
                raise AuthError("Account not found", 404)
            profile = decrypt_profile(session.data_key, record["profile_blob"])
        return {"username": session.username, "profile": profile}

    async def put_bio(self, token: str | None, profile: dict[str, Any]) -> dict[str, Any]:
        session = self.session(token)
        clean = sanitize_profile(profile)
        async with self._lock:
            record = self._read_user(session.username)
            if record is None:
                raise AuthError("Account not found", 404)
            record["profile_blob"] = encrypt_profile(session.data_key, clean)
            self._write_user(record)
        return {"username": session.username, "profile": clean}

    def _create_session(self, user_id: str, username: str, data_key: bytes) -> Session:
        token = secrets.token_urlsafe(32)
        session = Session(
            token=token,
            user_id=user_id,
            username=username,
            data_key=data_key,
            expires_unix=_now() + 12 * 3600,
        )
        self._sessions[token] = session
        return session
