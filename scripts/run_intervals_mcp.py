"""以项目 data/userinfo.json 中的凭据启动 intervals-mcp-server（stdio 传输）。

这样 API Key 只保留在 data/userinfo.json 一处，不必复制进 DSH 的 MCP 配置
（C:\\Users\\ai327\\.dsh\\profiles\\desktop\\cordis.patch.yml）。

被 DSH 作为 MCP stdio 服务器拉起时使用：
    .venv\\Scripts\\python.exe scripts\\run_intervals_mcp.py
"""
from __future__ import annotations

import json
import os
import pathlib
import runpy
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]


def main() -> None:
    info = json.loads((PROJECT_ROOT / "data" / "userinfo.json").read_text(encoding="utf-8"))
    api_key = str(info.get("API_Key", "")).strip()
    athlete_id = str(info.get("userid", "")).strip()
    if not api_key or not athlete_id:
        raise SystemExit("data/userinfo.json 缺少 API_Key 或 userid 字段")

    # 显式传入优先于已有环境变量，避免误用外部残留值
    os.environ["API_KEY"] = api_key
    os.environ["ATHLETE_ID"] = athlete_id
    os.environ.setdefault("MCP_TRANSPORT", "stdio")

    sys.argv = ["intervals-mcp-server"]
    runpy.run_module("intervals_mcp_server.server", run_name="__main__")


if __name__ == "__main__":
    main()
