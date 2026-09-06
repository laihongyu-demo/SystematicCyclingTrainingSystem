"""凭据服务：加密存储、读取与状态查询。

设计依据（FR-9.5 / §8.3）：
- 明文仅出现在内存中，落库一律为 AES-256-GCM 密文；
- 对外只暴露掩码（如 ****ljzc），页面与日志不得回显明文。
"""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Credential
from app.utils.crypto import decrypt, encrypt

SENSITIVE_KEYS = ("api_key", "apikey", "secret", "token", "key", "password")


def mask_secret(value: str) -> str:
    """显示末 4 位，其余打码；短值整体打码。"""
    if len(value) <= 4:
        return "****"
    return f"****{value[-4:]}"


class CredentialService:
    def __init__(self, session: Session, key: bytes) -> None:
        self._session = session
        self._key = key

    def upsert(self, provider: str, payload: dict, name: str = "default") -> Credential:
        if not isinstance(payload, dict) or not payload:
            raise ValueError("payload 必须是非空 dict")
        data_enc = encrypt(self._key, json.dumps(payload, ensure_ascii=False))
        row = self._session.scalar(
            select(Credential).where(
                Credential.provider == provider, Credential.name == name
            )
        )
        if row is None:
            row = Credential(provider=provider, name=name, data_enc=data_enc)
            self._session.add(row)
        else:
            row.data_enc = data_enc
            row.key_version += 1
        self._session.commit()
        self._session.refresh(row)
        return row

    def get(self, provider: str, name: str = "default") -> dict | None:
        row = self._session.scalar(
            select(Credential).where(
                Credential.provider == provider, Credential.name == name
            )
        )
        if row is None:
            return None
        return json.loads(decrypt(self._key, row.data_enc))

    def get_masked(self, provider: str, name: str = "default") -> dict | None:
        payload = self.get(provider, name)
        if payload is None:
            return None
        masked: dict = {}
        for k, v in payload.items():
            if isinstance(v, str) and any(s in k.lower() for s in SENSITIVE_KEYS):
                masked[k] = mask_secret(v)
            else:
                masked[k] = v
        return masked

    def status(self) -> list[dict]:
        rows = self._session.scalars(select(Credential).order_by(Credential.provider)).all()
        out: list[dict] = []
        for row in rows:
            masked = self.get_masked(row.provider, row.name) or {}
            out.append(
                {
                    "provider": row.provider,
                    "name": row.name,
                    "key_version": row.key_version,
                    "masked": masked,
                    "updated_at": row.updated_at.isoformat(),
                }
            )
        return out

    def delete(self, provider: str, name: str = "default") -> bool:
        row = self._session.scalar(
            select(Credential).where(
                Credential.provider == provider, Credential.name == name
            )
        )
        if row is None:
            return False
        self._session.delete(row)
        self._session.commit()
        return True
