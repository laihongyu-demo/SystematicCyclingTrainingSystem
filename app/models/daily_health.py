"""每日健康快照表（intervals.icu wellness -> 本地镜像，M2.5）。

设计依据（FR-2.1.3 / §6.3 M2.5）：
- 以天为粒度镜像 wellness 的健康字段：静息心率(RHR, icu 原始，全天监控)、
  HRV(rMSSD) 与 hrvSDNN、体重、体脂；
- 字段名以 M2.5-1 spike 实测为准：restingHR / hrv / hrvSDNN / weight / bodyFat；
- 睡眠字段族（sleepSecs/sleepScore/avgSleepingHR 等）不纳入首期（CHG-005）。
- 幂等语义与 daily_fitness 一致：按 date upsert，值不变则不动。
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.store.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class DailyHealth(Base):
    __tablename__ = "daily_health"

    date: Mapped[str] = mapped_column(String(10), primary_key=True)  # 运动员本地日期
    resting_rhr: Mapped[float | None] = mapped_column(Float)  # icu 原始 RHR(restingHR)
    hrv: Mapped[float | None] = mapped_column(Float)  # icu hrv（rMSSD）
    hrv_sdnn: Mapped[float | None] = mapped_column(Float)  # icu hrvSDNN
    weight: Mapped[float | None] = mapped_column(Float)  # icu weight（kg）
    fat_percent: Mapped[float | None] = mapped_column(Float)  # icu bodyFat（%）
    source: Mapped[str] = mapped_column(String(16), default="icu")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
