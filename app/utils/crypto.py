"""密钥与加解密工具（AES-256-GCM）。

- 加密主密钥存于 data/private/sct.key（data/ 整体不入版本库）；
- token 格式带版本前缀 `v1:`，便于未来做密钥轮换/迁移；
- 本模块不落盘任何明文，解密结果仅驻留内存。
"""
from __future__ import annotations

import base64
import secrets
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

TOKEN_PREFIX = "v1:"
NONCE_BYTES = 12


def load_or_create_key(path: Path) -> bytes:
    if path.exists():
        raw = path.read_bytes()
        if len(raw) != 32:
            raise ValueError(f"加密密钥文件长度非法（应为 32 字节）: {path}")
        return raw
    path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_bytes(32)
    path.write_bytes(key)
    return key


def encrypt(key: bytes, plaintext: str) -> str:
    nonce = secrets.token_bytes(NONCE_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return TOKEN_PREFIX + base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt(key: bytes, token: str) -> str:
    if not token.startswith(TOKEN_PREFIX):
        raise ValueError(f"不支持的密文版本前缀: {token[:8]}…")
    blob = base64.urlsafe_b64decode(token[len(TOKEN_PREFIX) :])
    nonce, ciphertext = blob[:NONCE_BYTES], blob[NONCE_BYTES:]
    return AESGCM(key).decrypt(nonce, ciphertext, None).decode("utf-8")
