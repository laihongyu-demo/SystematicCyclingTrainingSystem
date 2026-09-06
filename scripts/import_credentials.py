"""首次导入 intervals.icu 凭据：userinfo.json -> AES-GCM 加密落库。

用法：.venv\\Scripts\\python scripts\\import_credentials.py
- userinfo.json 已在 .gitignore，导入后可自行删除明文文件；
- 页面/日志仅展示掩码（末 4 位）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.config import settings
from app.services.credential_service import CredentialService, mask_secret
from app.store.db import SessionLocal, init_db
from app.utils.crypto import load_or_create_key

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    init_db()
    src = settings.data_dir / "userinfo.json"
    if not src.exists():
        print("缺少 data/userinfo.json（data/ 已在 .gitignore，仅限本机）。")
        return 1
    info = json.loads(src.read_text(encoding="utf-8"))
    userid = str(info.get("userid", "")).strip()
    api_key = str(info.get("API_Key", "")).strip()
    if not userid or not api_key:
        print("userinfo.json 缺少 userid 或 API_Key。")
        return 1

    key = load_or_create_key(settings.encryption_key_file)
    with SessionLocal() as session:
        service = CredentialService(session, key)
        service.upsert("intervals", {"userid": userid, "api_key": api_key})
    print(
        f"已加密保存 intervals 凭据：userid={userid}  api_key={mask_secret(api_key)}  "
        f"-> {settings.db_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
