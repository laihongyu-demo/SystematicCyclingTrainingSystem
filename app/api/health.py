"""健康检查与凭据状态查询（仅回显掩码）。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.services.credential_service import CredentialService
from app.store.db import get_db
from app.utils.crypto import load_or_create_key

router = APIRouter(prefix="/api")
Db = Annotated[Session, Depends(get_db)]


@router.get("/health")
def health(session: Db) -> dict:
    db_ok = session.execute(text("SELECT 1")).scalar() == 1
    return {"status": "ok" if db_ok else "degraded", "db": db_ok, "app": settings.app_name}


@router.get("/credentials/status")
def credential_status(session: Db) -> dict:
    service = CredentialService(session, load_or_create_key(settings.encryption_key_file))
    return {"providers": service.status()}
