"""晨起 RHR 表（M2.5，FR-2.1.4）。

- 用户**手动录入**：清晨清醒后，用手表/心率设备持续测量 5 分钟取最终值；
- 按天 1 条（date 主键天然约束）；**仅本地存储，不回写 intervals.icu**；
- 同天覆盖由 API 层要求显式确认（见 app/api/wellness.py），此处不记录审计。
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.store.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class MorningRhr(Base):
    __tablename__ = "morning_rhr"

    date: Mapped[str] = mapped_column(String(10), primary_key=True)  # 运动员本地日期
    value: Mapped[float] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
