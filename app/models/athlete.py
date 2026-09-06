"""运动员档案镜像表（M2.5，FR-2.1.2 / §6.3 athlete 扩展）。

- 从 intervals.icu `GET /athlete/0` 同步：保留各运动 FTP 设置的 JSON 快照，
  能力指标（FTP/eFTP/w·kg⁻¹）读取它计算（w/kg = FTP ÷ 体重）；
- 体重优先取最新 daily_health（wellness），此处 `weight` 仅作档案侧快照；
- 单机单运动员：remote_id 即 intervals.icu userid（形如 i93790），按需 upsert。
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.store.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Athlete(Base):
    __tablename__ = "athlete"

    remote_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(128))
    sport_settings_json: Mapped[str | None] = mapped_column(Text)  # 各运动 FTP 等设置快照
    weight: Mapped[float | None] = mapped_column(Float)  # 档案侧体重快照（kg）
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
