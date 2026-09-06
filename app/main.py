"""FastAPI 应用入口。

启动：python scripts/dev.py 或 uvicorn app.main:app
安全基线：仅绑定 127.0.0.1（见设计文档 §8）；页面与 /api 同源提供。
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles

from app.api import activities, health, metrics, sync
from app.config import settings
from app.store.db import init_db


def _frontend_dir() -> Path:
    """同源页面目录：优先 React 生产构建 web/dist，缺省回退 M1 控制台静态页。"""
    dist = settings.web_dist_dir
    if (dist / "index.html").is_file():
        return dist
    return settings.static_dir


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
app.include_router(sync.router)
app.include_router(metrics.router)
app.include_router(activities.router)


@app.get("/favicon.ico", include_in_schema=False)
def favicon_ico() -> Response:
    # 页面已声明 favicon.svg；兼容个别浏览器对 /favicon.ico 的默认探测
    return Response(status_code=204)


# 同源前端：优先 React 构建产物（web/dist），否则回退 M1 控制台静态页
app.mount("/", StaticFiles(directory=_frontend_dir(), html=True), name="static")
