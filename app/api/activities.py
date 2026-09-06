"""活动列表 API（M2-2）：按时间窗口返回活动摘要（倒序）。"""
from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.services.metrics_service import MetricsService
from app.store.db import get_db
from app.utils.dates import local_today

router = APIRouter(prefix="/api")
Db = Annotated[Session, Depends(get_db)]


@router.get("/activities")
def list_activities(
    session: Db,
    oldest: str | None = None,
    newest: str | None = None,
    days: int = Query(default=30, ge=1, le=730),
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict:
    newest_d = newest or local_today().isoformat()
    oldest_d = oldest or (local_today() - timedelta(days=days)).isoformat()
    return MetricsService(session).activities(oldest_d, newest_d, limit)
