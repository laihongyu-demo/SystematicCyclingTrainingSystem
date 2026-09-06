"""每日官方体能快照表（intervals.icu wellness -> 本地镜像）。

设计依据（G2 Bug1 修复）：intervals.icu 在 wellness 日记录中给出每个本地日期
计算完成的官方 CTL/ATL（当日含当天活动负荷、无活动日按官方口径衰减，“进行中的
今天”为截至请求时刻的实时值）。这些值就是 intervals.icu 站点 Fitness/Form 卡与
体能曲线展示的数字。直接镜像它们，可保证本系统当前值与官网零误差，
避免用本地指数衰减复算“今天”造成的口径偏差（ATL 短期常数误差会被放大）。
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.store.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class DailyFitness(Base):
    __tablename__ = "daily_fitness"

    date: Mapped[str] = mapped_column(String(10), primary_key=True)  # 运动员本地日期
    ctl: Mapped[float | None] = mapped_column(Float)
    atl: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(16), default="icu")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
