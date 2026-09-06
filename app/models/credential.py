"""凭据加密存储模型。

设计依据（系统设计文档 §8.3 / FR-9.5）：
- 明文 API Key 仅在本模块加密后落库，页面/日志只展示掩码；
- provider+name 唯一：intervals 为 (intervals, default)，LLM 供应商为 (llm, <vendor>:<model>)。
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.store.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Credential(Base):
    __tablename__ = "credential"
    __table_args__ = (
        UniqueConstraint("provider", "name", name="uq_credential_provider_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(64), default="default")
    data_enc: Mapped[str] = mapped_column(String(4096))
    key_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
