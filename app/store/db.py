"""SQLite 引擎与会话。

- WAL 模式 + busy_timeout：允许读写并发，避免“database is locked”；
- 外键开启；Base 供所有 ORM 模型继承。
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record) -> None:  # noqa: ANN001
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def _add_missing_columns() -> None:
    """SQLite 轻量演进：为新加列做幂等 ALTER（暂未引入 alembic）。"""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "activity_mirror" not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns("activity_mirror")}
    if "average_watts" not in existing:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE activity_mirror ADD COLUMN average_watts FLOAT"))


def init_db() -> None:
    """建表入口（本地单机 SQLite，首启 create_all；后续引入 alembic 管理演进）。"""
    settings.ensure_dirs()
    from app import models  # noqa: F401  确保模型已注册

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()
