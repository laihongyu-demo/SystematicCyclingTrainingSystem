"""FastAPI 应用入口。

启动：python scripts/dev.py 或 uvicorn app.main:app
安全基线：仅绑定 127.0.0.1（见设计文档 §8）；页面与 /api 同源提供。
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import health
from app.config import settings
from app.store.db import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
)

app.include_router(health.router)

# 同源前端静态页（Web 层引入 React 前的最小占位）
app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="static")
