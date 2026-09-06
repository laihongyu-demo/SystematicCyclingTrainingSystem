"""健康中心 API（M2.5，FR-2.1.3/2.1.4）。

- GET  /api/wellness/daily            健康日数据（HRV/RHR/体重/体脂，天粒度）
- GET  /api/wellness/morning-rhr      晨起 RHR 列表（含与昨日差值，日历天口径）
- POST /api/wellness/morning-rhr      晨起 RHR 录入（同天已有需 overwrite 确认）
- GET/PUT/DELETE /api/wellness/morning-rhr/{date}  单日读/改/删
"""
from __future__ import annotations

import re
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.services.metrics_service import MetricsService
from app.store.db import get_db
from app.utils.dates import local_today

router = APIRouter(prefix="/api/wellness")
Db = Annotated[Session, Depends(get_db)]

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _check_date(day: str) -> str:
    if not DATE_RE.match(day):
        raise HTTPException(status_code=422, detail="date 需为 YYYY-MM-DD")
    return day


def _window(oldest: str | None, newest: str | None, days: int) -> tuple[str, str]:
    newest = newest or local_today().isoformat()
    oldest = oldest or (local_today() - timedelta(days=days)).isoformat()
    return oldest, newest


class MorningRhrIn(BaseModel):
    value: float = Field(ge=20, le=250, description="晨起静息心率（bpm）")
    note: str | None = Field(default=None, max_length=200)

    @field_validator("note")
    @classmethod
    def _blank_note(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            return None
        return v.strip() if v else v


class MorningRhrCreate(MorningRhrIn):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    overwrite: bool = False  # 同天已有记录时需显式确认覆盖


@router.get("/daily")
def daily(
    session: Db,
    oldest: str | None = None,
    newest: str | None = None,
    days: int = Query(default=30, ge=7, le=730),
) -> dict:
    lo, hi = _window(oldest, newest, days)
    return MetricsService(session).health_daily(lo, hi)


@router.get("/morning-rhr")
def morning_rhr_list(
    session: Db,
    oldest: str | None = None,
    newest: str | None = None,
    days: int = Query(default=30, ge=1, le=730),
) -> dict:
    lo, hi = _window(oldest, newest, days)
    return MetricsService(session).morning_rhr_series(lo, hi)


@router.post("/morning-rhr")
def morning_rhr_upsert(payload: MorningRhrCreate, session: Db) -> dict:
    result = MetricsService(session).morning_rhr_upsert(
        payload.date, payload.value, payload.note, overwrite=payload.overwrite
    )
    if result["status"] == "conflict":
        raise HTTPException(
            status_code=409,
            detail=f"{payload.date} 已有晨起 RHR {result['existing']['value']}，确认覆盖请传 overwrite=true",
        )
    return result


@router.get("/morning-rhr/{day}")
def morning_rhr_get(day: str, session: Db) -> dict:
    _check_date(day)
    data = MetricsService(session).morning_rhr_series(day, day)
    if not data["items"]:
        raise HTTPException(status_code=404, detail=f"{day} 无晨起 RHR 记录")
    return data["items"][0]


@router.put("/morning-rhr/{day}")
def morning_rhr_put(day: str, payload: MorningRhrIn, session: Db) -> dict:
    _check_date(day)
    return MetricsService(session).morning_rhr_upsert(
        day, payload.value, payload.note, overwrite=True
    )


@router.delete("/morning-rhr/{day}")
def morning_rhr_delete(day: str, session: Db) -> dict:
    _check_date(day)
    if not MetricsService(session).morning_rhr_delete(day):
        raise HTTPException(status_code=404, detail=f"{day} 无晨起 RHR 记录")
    return {"deleted": True, "date": day}
