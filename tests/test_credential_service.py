"""凭据服务单元测试（T1）：加密存储、掩码、幂等 upsert。"""
from __future__ import annotations

from app.models import Credential
from app.services.credential_service import CredentialService, mask_secret


def test_upsert_get_roundtrip(session, enc_key):
    svc = CredentialService(session, enc_key)
    svc.upsert("intervals", {"userid": "i93790", "api_key": "plain-secret-value"})
    payload = svc.get("intervals")
    assert payload == {"userid": "i93790", "api_key": "plain-secret-value"}


def test_db_never_stores_plaintext(session, enc_key):
    svc = CredentialService(session, enc_key)
    svc.upsert("intervals", {"userid": "i93790", "api_key": "PLAINTEXT-KEY-1234"})
    from sqlalchemy import text

    raw = session.execute(text("SELECT data_enc FROM credential")).scalar_one()
    assert "PLAINTEXT-KEY-1234" not in raw
    assert raw.startswith("v1:")


def test_upsert_increments_key_version(session, enc_key):
    svc = CredentialService(session, enc_key)
    svc.upsert("intervals", {"userid": "u", "api_key": "k1"})
    v1 = svc.get("intervals")
    svc.upsert("intervals", {"userid": "u", "api_key": "k2"})
    rows = session.query(Credential).all()
    assert len(rows) == 1
    assert rows[0].key_version == 2
    assert v1 != svc.get("intervals")


def test_masked_and_status_no_plaintext(session, enc_key):
    svc = CredentialService(session, enc_key)
    svc.upsert("intervals", {"userid": "i93790", "api_key": "abcdef123456"})
    masked = svc.get_masked("intervals")
    assert masked["api_key"] == "****3456"
    status = svc.status()
    text = str(status)
    assert "abcdef123456" not in text
    assert "3456" in text


def test_delete_and_missing(session, enc_key):
    svc = CredentialService(session, enc_key)
    assert svc.get("nope") is None
    svc.upsert("intervals", {"userid": "u", "api_key": "k"})
    assert svc.delete("intervals") is True
    assert svc.delete("intervals") is False


def test_mask_secret_short(session, enc_key):
    assert mask_secret("ab") == "****"
    assert mask_secret("abcdef") == "****cdef"
