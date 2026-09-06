"""S0-3 intervals.icu 认证 spike（只读）.

结论（2026-09-05 实测）：
- 认证方式 = HTTP Basic；用户名必须为字面量 API_KEY，密码 = 个人 API key；
  athlete 路径用 0 表示“凭据所属本人”。
- 只读端点 /api/v1/athlete/0 返回个人信息；/athlete/0/activities 返回完成活动概要。

用法：.venv\\Scripts\\python scripts\\spike_intervals_auth.py [--no-net]
凭据从仓库根 userinfo.json 读取（该文件已被 gitignore，不入库），全程不打印明文。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://intervals.icu/api/v1"


def load_creds() -> tuple[str, str]:
    cfg = json.loads((ROOT / "userinfo.json").read_text(encoding="utf-8"))
    return cfg["userid"], cfg["API_Key"]


def attempt(
    client: httpx.Client,
    label: str,
    auth,
    headers: dict | None = None,
    path: str = "0",
) -> None:
    t0 = time.perf_counter()
    try:
        r = client.get(f"{BASE}/athlete/{path}", auth=auth, headers=headers or {})
        dt = (time.perf_counter() - t0) * 1000
        body_preview = ""
        if r.status_code == 200:
            data = r.json()
            body_preview = json.dumps(
                {k: data[k] for k in list(data)[:12]}, ensure_ascii=False
            )[:400]
        print(f"[{label}] HTTP {r.status_code} {dt:.0f}ms | {body_preview or r.text[:200]}")
    except Exception as exc:  # noqa: BLE001
        print(f"[{label}] EXC {type(exc).__name__}: {exc}")


def probe_contracts(client: httpx.Client) -> None:
    """认证成功后抓取少量只读契约样例（脱敏落盘到 data/spike，不入库）。"""
    auth = ("API_KEY", api_key)
    endpoints = [
        ("athlete", "/athlete/0"),
        ("activities[90d]", "/athlete/0/activities?newest=2026-09-05&oldest=2026-06-08"),
    ]
    for label, path in endpoints:
        t0 = time.perf_counter()
        r = client.get(f"{BASE}{path}", auth=auth, timeout=60)
        dt = (time.perf_counter() - t0) * 1000
        if r.status_code != 200:
            print(f"[{label}] HTTP {r.status_code} {r.text[:200]}")
            continue
        out_dir = ROOT / "data" / "spike"
        out_dir.mkdir(parents=True, exist_ok=True)
        name = path.split("?")[0].strip("/").replace("/", "_") or "root"
        (out_dir / f"{name}.json").write_text(
            json.dumps(r.json(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        data = r.json()
        summary = {}
        if isinstance(data, list):
            summary = {"count": len(data)}
            if data:
                summary["first_id"] = data[0].get("id")
                summary["keys_sample"] = list(data[0])[:20]
        else:
            summary = {
                "id": data.get("id"),
                "name": data.get("name"),
                "keys_sample": list(data)[:25],
            }
        preview = json.dumps(summary, ensure_ascii=False)[:300]
        print(f"[{label}] HTTP 200 {dt:.0f}ms saved -> data/spike/{name}.json | {preview}")


if __name__ == "__main__":
    userid, api_key = load_creds()
    mask = api_key[-4:]
    print(f"userid={userid} key=****{mask}")
    if "--no-net" not in sys.argv:
        with httpx.Client(timeout=20) as client:
            # 官方约定：Basic 用户名固定为字面量 API_KEY，密码 = 个人 API key；athlete 路径用 0
            attempt(client, "basic(API_KEY,key) p=0", ("API_KEY", api_key), path="0")
            # 反例：用户名用真实 userid（应失败）
            attempt(client, "basic(userid,key) p=0", (userid, api_key), path="0")
            # 认证成功后抓契约样例
            probe_contracts(client)
    print("done")
