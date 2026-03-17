from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _get_fernet() -> Fernet:
    key_material = get_settings().secret_key.encode("utf-8")
    fernet_key = base64.urlsafe_b64encode(hashlib.sha256(key_material).digest())
    return Fernet(fernet_key)


def encrypt_token(token: str) -> bytes:
    if not token:
        raise ValueError("token cannot be empty")
    return _get_fernet().encrypt(token.encode("utf-8"))


def decrypt_token(encrypted_token: bytes | str | None) -> str:
    if not encrypted_token:
        raise ValueError("encrypted_token cannot be empty")

    try:
        if isinstance(encrypted_token, str):
            encrypted_token = encrypted_token.encode("utf-8")

        return _get_fernet().decrypt(encrypted_token).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Invalid encrypted token") from exc