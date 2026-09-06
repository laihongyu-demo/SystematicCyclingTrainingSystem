"""SCT 全局配置（pydantic-settings）。

读取顺序：默认值 <- 项目根 .env <- 环境变量（前缀 SCT_）。
本模块不含任何机密；API Key 等一律走加密凭据存储（app/services/credential_service.py）。
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCT_", env_file=".env", extra="ignore")

    app_name: str = "Systematic Cycling Training System"
    version: str = "0.1.0"
    # 安全基线：仅本机可访问（见设计文档 §8 安全策略）
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False

    data_dir: Path = PROJECT_ROOT / "data"

    # 启动后是否自动唤起浏览器（仅 dev 直接运行且非 reload 时生效）
    open_browser: bool = True

    @property
    def db_path(self) -> Path:
        return self.data_dir / "sct.db"

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path.as_posix()}"

    @property
    def encryption_key_file(self) -> Path:
        return self.data_dir / "private" / "sct.key"

    @property
    def library_dir(self) -> Path:
        return self.data_dir / "library"

    @property
    def static_dir(self) -> Path:
        return PROJECT_ROOT / "app" / "static"

    def ensure_dirs(self) -> None:
        for p in (self.data_dir, self.encryption_key_file.parent, self.library_dir):
            p.mkdir(parents=True, exist_ok=True)


settings = Settings()
