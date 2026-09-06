"""开发启动入口（一条命令：python scripts/dev.py）。

按设计文档 §8 安全基线仅绑定 127.0.0.1。
"""
from __future__ import annotations

import uvicorn

from app.config import settings


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )


if __name__ == "__main__":
    main()
