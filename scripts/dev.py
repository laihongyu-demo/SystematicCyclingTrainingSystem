"""开发启动入口（一条命令：python -m scripts.dev）。

- 按设计文档 §8 安全基线仅绑定 127.0.0.1；
- 默认在服务就绪后自动唤起浏览器（可用 SCT_OPEN_BROWSER=0 关闭；reload 模式不唤起）。
"""
from __future__ import annotations

import threading
import webbrowser

import uvicorn

from app.config import settings


def main() -> None:
    url = f"http://{settings.host}:{settings.port}"
    if settings.open_browser and not settings.reload:
        threading.Timer(1.2, lambda: webbrowser.open(url, new=2)).start()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )


if __name__ == "__main__":
    main()
