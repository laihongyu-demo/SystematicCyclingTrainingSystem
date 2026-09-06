"""同步 API（M1-5）：手动触发活动同步 + 最近同步状态查询。"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.integrations.intervals.client import (
    IntervalsAuthError,
    IntervalsClient,
    IntervalsError,
)
from app.models import SyncLog
from app.services.credential_service import CredentialService
from app.services.sync_service import DEFAULT_DAYS, SyncService
from app.store.db import get_db
from app.utils.crypto import load_or_create_key

router = APIRouter(prefix="/api")
Db = Annotated[Session, Depends(get_db)]


class SyncRequest(BaseModel):
    oldest: str | None = None  # YYYY-MM-DD
    newest: str | None = None  # YYYY-MM-DD


def _client_for(session: Session) -> IntervalsClient:
    service = CredentialService(
        session, load_or_create_key(settings.encryption_key_file)
    )
    creds = service.get("intervals")
    if not creds or not creds.get("api_key"):
        raise HTTPException(status_code=409, detail="尚未配置 intervals.icu 凭据")
    return IntervalsClient(creds["api_key"])


@router.get("/sync/status")
def sync_status(session: Db) -> dict:
    logs = session.scalars(
        select(SyncLog).order_by(SyncLog.id.desc()).limit(10)
    ).all()
    return {"recent": [SyncService._log_summary(log) for log in logs]}


@router.post("/sync/activities")
def run_activity_sync(payload: SyncRequest, session: Db) -> dict:
    newest = payload.newest or datetime.now(UTC).date().isoformat()
    oldest = payload.oldest or (
        datetime.now(UTC).date() - timedelta(days=DEFAULT_DAYS)
    ).isoformat()
    client = _client_for(session)
    try:
        return SyncService(session, client).sync_activities(oldest, newest)
    except IntervalsAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except IntervalsError as exc:
        raise HTTPException(status_code=502, detail=f"intervals.icu 同步失败: {exc}") from exc
