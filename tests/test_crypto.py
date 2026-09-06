"""加解密单元测试（T1）。"""
from __future__ import annotations

import pytest
from cryptography.exceptions import InvalidTag

from app.utils.crypto import decrypt, encrypt

KEY = bytes(range(32))


def test_roundtrip_unicode():
    token = encrypt(KEY, "API_Key: 3k5v8swm22ozw5x3h69zmljzc 中文/¥")
    assert decrypt(KEY, token) == "API_Key: 3k5v8swm22ozw5x3h69zmljzc 中文/¥"


def test_token_randomized():
    a = encrypt(KEY, "same")
    b = encrypt(KEY, "same")
    assert a != b


def test_wrong_key_rejected():
    token = encrypt(KEY, "secret")
    with pytest.raises(InvalidTag):
        decrypt(bytes(32), token)


def test_tampered_token_rejected():
    token = encrypt(KEY, "secret")
    body = bytearray(token.encode("ascii"))
    body[-1] = b"A"[0] if body[-1] != b"A"[0] else b"B"[0]
    with pytest.raises((InvalidTag, ValueError)):
        decrypt(KEY, body.decode("ascii"))


def test_unsupported_prefix_rejected():
    with pytest.raises(ValueError):
        decrypt(KEY, "v2:AAAA")
