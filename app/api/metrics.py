"""指标 API（M2-1）：体能曲线 / 周负荷汇总 / 概览。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.services.metrics_service import MetricsService
from app.store.db import get_db

router = APIRouter(prefix="/api/metrics")
Db = Annotated[Session, Depends(get_db)]


def _default_window(days: int) -> tuple[str, str]:
    newest = datetime.now(UTC).date()
    return (newest - timedelta(days=days)).isoformat(), newest.isoformat()


@router.get("/fitness")
def fitness(
    session: Db,
    oldest: str | None = None,
    newest: str | None = None,
    mode: str = Query(default="smooth", pattern="^(points|smooth)$"),
    days: int = Query(default=90, ge=7, le=730),
) -> dict:
    lo, hi = _default_window(days)
    oldest = oldest or lo
    newest = newest or hi
    series = MetricsService(session).fitness_series(oldest, newest, mode)
    return {"mode": mode, "window": {"oldest": oldest, "newest": newest}, "series": series}


@router.get("/weekly")
def weekly(
    session: Db,
    oldest: str | None = None,
    newest: str | None = None,
    days: int = Query(default=90, ge=7, le=730),
) -> dict:
    lo, hi = _default_window(days)
    oldest = oldest or lo
    newest = newest or hi
    return {
        "window": {"oldest": oldest, "newest": newest},
        "weeks": MetricsService(session).weekly(oldest, newest),
    }


@router.get("/calendar")
def calendar_days(
    session: Db,
    oldest: str | None = None,
    newest: str | None = None,
    days: int = Query(default=30, ge=7, le=730),
) -> dict:
    lo, hi = _default_window(days)
    oldest = oldest or lo
    newest = newest or hi
    return {
        "window": {"oldest": oldest, "newest": newest},
        "days": MetricsService(session).day_aggregate(oldest, newest),
    }


@router.get("/overview")
def overview(
    session: Db,
    days: int = Query(default=90, ge=7, le=730),
) -> dict:
    return MetricsService(session).overview(days)
