"""同步服务（M1-3）：intervals 活动 -> activity_mirror 幂等同步。

幂等语义：以外部 id 为主键；核心字段 sha1 未变则不动，变了才更新；
“重复同步一致”可通过第二次同步 unchanged=全部、inserted=0 断言。
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.intervals.client import IntervalsClient
from app.integrations.intervals.mapping import map_activity
from app.models import ActivityMirror, SyncLog

DEFAULT_DAYS = 90


class SyncService:
    def __init__(self, session: Session, client: IntervalsClient) -> None:
        self._session = session
        self._client = client

    def _resolve_client(self) -> IntervalsClient:
        if self._client is None:
            raise RuntimeError("SyncService 需要注入已认证的 IntervalsClient")
        return self._client

    @staticmethod
    def default_window(days: int = DEFAULT_DAYS) -> tuple[date, date]:
        newest = datetime.now(UTC).date()
        return newest - timedelta(days=days), newest

    def sync_activities(self, oldest: str, newest: str) -> dict:
        log = SyncLog(scope="activities", window_oldest=oldest, window_newest=newest)
        self._session.add(log)
        self._session.commit()
        self._session.refresh(log)
        try:
            client = self._resolve_client()
            raw_list = client.list_activities(oldest, newest)
            rows = [map_activity(item) for item in raw_list]
            counts, updated_ids = self._apply_upsert(rows)

            log.fetched = len(rows)
            log.inserted = counts["inserted"]
            log.updated = counts["updated"]
            log.unchanged = counts["unchanged"]
            log.finished_at = datetime.now(UTC)
            log.status = "success"
            self._session.commit()
            return self._log_summary(log)
        except Exception as exc:  # noqa: BLE001
            self._session.rollback()
            log.status = "failed"
            log.error = str(exc)[:2000]
            log.finished_at = datetime.now(UTC)
            self._session.commit()
            raise

    def _apply_upsert(self, rows: list[dict]) -> tuple[dict, list[str]]:
        ids = [r["id"] for r in rows]
        existing_rows = self._session.scalars(
            select(ActivityMirror).where(ActivityMirror.id.in_(ids))
        ).all()
        existing = {r.id: r for r in existing_rows}

        inserted = updated = unchanged = 0
        for row in rows:
            current = existing.get(row["id"])
            if current is None:
                self._session.add(ActivityMirror(**row))
                inserted += 1
            elif current.content_hash != row["content_hash"]:
                for key, value in row.items():
                    setattr(current, key, value)
                updated += 1
            else:
                unchanged += 1
        self._session.flush()
        return {"inserted": inserted, "updated": updated, "unchanged": unchanged}, ids

    @staticmethod
    def _log_summary(log: SyncLog) -> dict:
        return {
            "id": log.id,
            "scope": log.scope,
            "status": log.status,
            "window": {"oldest": log.window_oldest, "newest": log.window_newest},
            "fetched": log.fetched,
            "inserted": log.inserted,
            "updated": log.updated,
            "unchanged": log.unchanged,
            "started_at": log.started_at.isoformat(),
            "finished_at": log.finished_at.isoformat() if log.finished_at else None,
            "error": log.error,
        }
