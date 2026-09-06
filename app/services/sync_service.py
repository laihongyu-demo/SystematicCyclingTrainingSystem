"""同步服务（M1-3）：intervals 活动 -> activity_mirror 幂等同步。

幂等语义：以外部 id 为主键；核心字段 sha1 未变则不动，变了才更新；
“重复同步一致”可通过第二次同步 unchanged=全部、inserted=0 断言。

G2 Bug1 补充：每次活动同步同时拉取 intervals 每日官方 CTL/ATL
（wellness 日记录，镜像到 daily_fitness），保证“当前值”与官网零误差。
"""
from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.intervals.client import IntervalsClient
from app.integrations.intervals.mapping import map_activity
from app.models import ActivityMirror, DailyFitness, SyncLog

DEFAULT_DAYS = 370  # 覆盖前端最长窗口(1年)并留余量
# 每次同步兜底拉取，保证体能曲线任意范围可展示
DAILY_FITNESS_LOOKBACK = 370


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
            fitness_counts = self._sync_daily_fitness(client, oldest, newest)

            log.fetched = len(rows)
            log.inserted = counts["inserted"]
            log.updated = counts["updated"]
            log.unchanged = counts["unchanged"]
            log.finished_at = datetime.now(UTC)
            log.status = "success"
            self._session.commit()
            summary = self._log_summary(log)
            summary["fitness"] = fitness_counts
            return summary
        except Exception as exc:  # noqa: BLE001
            self._session.rollback()
            log.status = "failed"
            log.error = str(exc)[:2000]
            log.finished_at = datetime.now(UTC)
            self._session.commit()
            raise

    def _sync_daily_fitness(self, client: IntervalsClient, oldest: str, newest: str) -> dict:
        """镜像 intervals 每日官方 CTL/ATL（幂等 upsert by date）。"""
        newest_d = date.fromisoformat(newest)
        oldest_d = min(date.fromisoformat(oldest), newest_d - timedelta(days=DAILY_FITNESS_LOOKBACK))
        raw = client.get_daily_fitness(oldest_d.isoformat(), newest_d.isoformat())
        incoming: dict[str, dict] = {}
        for item in raw:
            day = item.get("id")
            if not isinstance(day, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) is None:
                continue
            ctl, atl = item.get("ctl"), item.get("atl")
            if ctl is None and atl is None:
                continue
            incoming[day] = {
                "ctl": float(ctl) if ctl is not None else None,
                "atl": float(atl) if atl is not None else None,
            }
        if not incoming:
            return {"inserted": 0, "updated": 0}

        existing = self._session.scalars(
            select(DailyFitness).where(DailyFitness.date.in_(list(incoming)))
        ).all()
        existing_map = {r.date: r for r in existing}
        inserted = updated = 0
        for day, values in incoming.items():
            row = existing_map.get(day)
            if row is None:
                self._session.add(DailyFitness(date=day, **values))
                inserted += 1
            elif row.ctl != values["ctl"] or row.atl != values["atl"]:
                row.ctl = values["ctl"]
                row.atl = values["atl"]
                row.updated_at = datetime.now(UTC)
                updated += 1
        self._session.flush()
        return {"inserted": inserted, "updated": updated}

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
