"""同步服务（M1-3 + M2.5）：intervals -> 本地镜像幂等同步。

幂等语义：以外部 id 为主键；核心字段 sha1 未变则不动，变了才更新；
“重复同步一致”可通过第二次同步 unchanged=全部、inserted=0 断言。

G2 Bug1 补充：每次活动同步同时拉取 intervals 每日官方 CTL/ATL
（wellness 日记录，镜像到 daily_fitness），保证“当前值”与官网零误差。

M2.5 扩展：同一 wellness 请求把健康字段（restingHR/hrv/hrvSDNN/weight/bodyFat）
镜像到 daily_health；并镜像运动员档案（FTP 设置）到 athlete 表。
"""
from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.intervals.client import IntervalsClient
from app.integrations.intervals.mapping import map_activity
from app.models import (
    ActivityMirror,
    Athlete,
    DailyFitness,
    DailyHealth,
    SyncLog,
)

DEFAULT_DAYS = 370  # 覆盖前端最长窗口(1年)并留余量
# 每次同步兜底拉取，保证体能/健康曲线任意范围可展示
DAILY_FITNESS_LOOKBACK = 370

# wellness 原始字段名 -> daily_health 列名（M2.5-1 spike 实测）
WELLNESS_HEALTH_FIELDS: dict[str, str] = {
    "restingHR": "resting_rhr",
    "hrv": "hrv",
    "hrvSDNN": "hrv_sdnn",
    "weight": "weight",
    "bodyFat": "fat_percent",
}


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
            wellness_counts = self._sync_daily_wellness(client, oldest, newest)
            self._sync_athlete_profile(client)

            log.fetched = len(rows)
            log.inserted = counts["inserted"]
            log.updated = counts["updated"]
            log.unchanged = counts["unchanged"]
            log.finished_at = datetime.now(UTC)
            log.status = "success"
            self._session.commit()
            summary = self._log_summary(log)
            summary["wellness"] = wellness_counts
            return summary
        except Exception as exc:  # noqa: BLE001
            self._session.rollback()
            log.status = "failed"
            log.error = str(exc)[:2000]
            log.finished_at = datetime.now(UTC)
            self._session.commit()
            raise

    def _sync_daily_wellness(self, client: IntervalsClient, oldest: str, newest: str) -> dict:
        """镜像 intervals 每日官方快照：CTL/ATL -> daily_fitness；健康字段 -> daily_health。

        两者均按 date 幂等 upsert；同日多行仅保留最后一行（wellness 一天一行，天然唯一）。
        """
        newest_d = date.fromisoformat(newest)
        oldest_d = min(date.fromisoformat(oldest), newest_d - timedelta(days=DAILY_FITNESS_LOOKBACK))
        raw = client.get_daily_wellness(oldest_d.isoformat(), newest_d.isoformat())

        health_incoming: dict[str, dict] = {}
        fitness_incoming: dict[str, dict] = {}
        for item in raw:
            day = item.get("id")
            if not isinstance(day, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) is None:
                continue
            ctl, atl = item.get("ctl"), item.get("atl")
            if ctl is not None or atl is not None:
                fitness_incoming[day] = {
                    "ctl": float(ctl) if ctl is not None else None,
                    "atl": float(atl) if atl is not None else None,
                }
            health_values = {
                col: _to_float(item.get(src)) for src, col in WELLNESS_HEALTH_FIELDS.items()
            }
            if any(v is not None for v in health_values.values()):
                health_incoming[day] = health_values
        if not fitness_incoming and not health_incoming:
            return {
                "fitness": {"inserted": 0, "updated": 0},
                "health": {"inserted": 0, "updated": 0},
            }

        counts = {
            "fitness": self._upsert_daily(
                DailyFitness, fitness_incoming, ("ctl", "atl")
            ),
            "health": self._upsert_daily(
                DailyHealth, health_incoming, tuple(WELLNESS_HEALTH_FIELDS.values())
            ),
        }
        self._session.flush()
        return counts

    def _upsert_daily(
        self, model, incoming: dict[str, dict], compare_cols: tuple[str, ...]
    ) -> dict:
        """按 date 主键幂等 upsert 通用实现（值一致则不动）。"""
        if not incoming:
            return {"inserted": 0, "updated": 0}
        existing = self._session.scalars(
            select(model).where(model.date.in_(list(incoming)))
        ).all()
        existing_map = {r.date: r for r in existing}
        inserted = updated = 0
        now = datetime.now(UTC)
        for day, values in incoming.items():
            row = existing_map.get(day)
            if row is None:
                self._session.add(model(date=day, **values))
                inserted += 1
                continue
            changed = any(getattr(row, col) != values[col] for col in compare_cols)
            if changed:
                for col in compare_cols:
                    setattr(row, col, values[col])
                row.updated_at = now
                updated += 1
        return {"inserted": inserted, "updated": updated}

    def _sync_athlete_profile(self, client: IntervalsClient) -> str | None:
        """镜像 athletes 档案（FTP 设置来源）：upsert 到 athlete 表。

        M2.5 FR-2.1.2：FTP 取 intervals 档案 sportSettings 各运动 FTP 设置；
        本表仅存快照，读取/口径计算在 metrics_service.capability() 完成。
        """
        profile = client.get_athlete()
        remote_id = str(profile.get("id") or "0")
        sport_settings = profile.get("sportSettings")
        row = self._session.get(Athlete, remote_id)
        if row is None:
            row = Athlete(remote_id=remote_id)
            self._session.add(row)
        row.sport_settings_json = (
            json.dumps(sport_settings, ensure_ascii=False)
            if isinstance(sport_settings, list)
            else None
        )
        weight = profile.get("icu_weight")
        if weight is None:
            weight = profile.get("weight")
        row.weight = _to_float(weight)
        first = (profile.get("firstname") or "").strip()
        last = (profile.get("lastname") or "").strip()
        row.display_name = f"{first} {last}".strip() or None
        row.last_synced_at = datetime.now(UTC)
        return remote_id

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


def _to_float(value: object) -> float | None:
    """wellness/档案数值转 float；空串/None/非法值一律归 None。"""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
