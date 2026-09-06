"""完成活动镜像表（intervals.icu -> 本地只读镜像）。

M1-3 幂等同步：id 为外部活动 id；content_hash 供变更检测。
原始载荷存 raw_json，便于后续扩展新列时不必重新抓取。
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.store.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ActivityMirror(Base):
    __tablename__ = "activity_mirror"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # 外部活动 id，如 i183491745
    athlete_id: Mapped[str | None] = mapped_column(String(32), index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    type: Mapped[str | None] = mapped_column(String(32), index=True)
    start_date_local: Mapped[str | None] = mapped_column(String(32), index=True)
    start_date_utc: Mapped[str | None] = mapped_column(String(32))
    moving_time_s: Mapped[int | None] = mapped_column(Integer)
    elapsed_time_s: Mapped[int | None] = mapped_column(Integer)
    distance_m: Mapped[float | None] = mapped_column(Float)
    elevation_gain_m: Mapped[float | None] = mapped_column(Float)
    trainer: Mapped[bool | None] = mapped_column(Boolean)
    device_name: Mapped[str | None] = mapped_column(String(64))
    device_watts: Mapped[bool | None] = mapped_column(Boolean)
    has_heartrate: Mapped[bool | None] = mapped_column(Boolean)
    average_heartrate: Mapped[float | None] = mapped_column(Float)
    max_heartrate: Mapped[float | None] = mapped_column(Float)
    average_cadence: Mapped[float | None] = mapped_column(Float)
    average_watts: Mapped[float | None] = mapped_column(Float)  # AP：intervals icu_average_watts
    weighted_avg_watts: Mapped[float | None] = mapped_column(Float)
    max_speed: Mapped[float | None] = mapped_column(Float)
    average_speed: Mapped[float | None] = mapped_column(Float)
    calories: Mapped[int | None] = mapped_column(Integer)
    trimp: Mapped[float | None] = mapped_column(Float)
    training_load: Mapped[float | None] = mapped_column(Float)
    atl: Mapped[float | None] = mapped_column(Float)
    ctl: Mapped[float | None] = mapped_column(Float)
    perceived_exertion: Mapped[int | None] = mapped_column(Integer)
    external_id: Mapped[str | None] = mapped_column(String(64))
    file_type: Mapped[str | None] = mapped_column(String(8))
    raw_json: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(40), index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
