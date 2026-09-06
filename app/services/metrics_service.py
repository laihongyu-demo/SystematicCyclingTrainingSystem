"""指标汇总服务（M2-1）：周负荷汇总 + CTL/ATL/TSB 曲线。

口径（G2 Bug1 修复后，与 intervals.icu 零误差）：
- 体能数值以 intervals.icu 每日官方快照为准（wellness 日记录 -> daily_fitness）。
  官方已含“活动日计入当日负荷、非活动日按口径衰减、进行中当日为实时值”，
  直接镜像官网数字，无需本地复算；
- 缺失日（本地快照窗口未覆盖时）才在相邻锚点间按标准指数衰减补全
  （CTL τ=42d、ATL τ=7d）；
- points 模式 = 每活动日官方快照（icu_ctl/icu_atl），TSB = CTL - ATL。
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActivityMirror, DailyFitness
from app.utils.dates import local_today

CTL_TAU_DAYS = 42.0
ATL_TAU_DAYS = 7.0


class MetricsService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ---------- 数据装载 ----------
    def _rows(self, oldest: str, newest: str) -> list[ActivityMirror]:
        return list(
            self._session.scalars(
                select(ActivityMirror)
                .where(
                    ActivityMirror.start_date_local >= f"{oldest}T00:00:00",
                    ActivityMirror.start_date_local < _next_day(newest),
                )
                .order_by(ActivityMirror.start_date_local)
            )
        )

    def _daily_rows(self, oldest: str, newest: str) -> dict[date, DailyFitness]:
        rows = self._session.scalars(
            select(DailyFitness).where(
                DailyFitness.date >= oldest, DailyFitness.date <= newest
            )
        ).all()
        return {date.fromisoformat(r.date): r for r in rows}

    # ---------- 体能曲线 ----------
    def fitness_series(
        self, oldest: str, newest: str, mode: str = "smooth"
    ) -> list[dict]:
        if mode not in {"points", "smooth"}:
            raise ValueError("mode 仅支持 points | smooth")
        rows = self._rows(oldest, newest)
        # 同一天保留最后一次活动后的官方快照（rows 已按时间升序）
        per_day: dict[date, ActivityMirror] = {}
        for row in rows:
            d = _local_date(row.start_date_local)
            if d is not None:
                per_day[d] = row
        daily: dict[date, DailyFitness] = self._daily_rows(oldest, newest)
        if not per_day and not daily:
            return []

        if mode == "points":
            return [_point(d, per_day[d], include_load=True) for d in sorted(per_day)]

        # smooth：以官方每日值为骨架，缺失日用相邻锚点衰减补全，
        # 活动日无每日记录时退回活动快照；延续到窗口最新日期。
        known_days = set(per_day) | set(daily)
        start = min(known_days)
        end = max(max(known_days), date.fromisoformat(newest))
        out: list[dict] = []
        current_ctl: float | None = None
        current_atl: float | None = None
        cursor = start
        while cursor <= end:
            fit = daily.get(cursor)
            row = per_day.get(cursor)
            if fit is not None:
                ctl_v = _num(fit.ctl)
                atl_v = _num(fit.atl)
                if ctl_v is not None:
                    current_ctl = ctl_v
                if atl_v is not None:
                    current_atl = atl_v
            elif row is not None:
                ctl_v = _num(row.ctl)
                atl_v = _num(row.atl)
                if ctl_v is not None:
                    current_ctl = ctl_v
                if atl_v is not None:
                    current_atl = atl_v
            elif current_ctl is not None and current_atl is not None:
                current_ctl *= math.exp(-1.0 / CTL_TAU_DAYS)
                current_atl *= math.exp(-1.0 / ATL_TAU_DAYS)
            if current_ctl is not None and current_atl is not None:
                out.append(_point(cursor, row, current_ctl, current_atl, include_load=True))
            cursor += timedelta(days=1)
        return out

    # ---------- 周负荷汇总 ----------
    def weekly(self, oldest: str, newest: str) -> list[dict]:
        rows = self._rows(oldest, newest)
        agg: dict[str, dict] = defaultdict(
            lambda: {
                "activities": 0,
                "distance_km": 0.0,
                "moving_h": 0.0,
                "load": 0.0,
                "trimp": 0.0,
            }
        )
        for row in rows:
            d = _local_date(row.start_date_local)
            if d is None:
                continue
            week = d - timedelta(days=d.weekday())
            a = agg[week.isoformat()]
            a["activities"] += 1
            if row.distance_m:
                a["distance_km"] += row.distance_m / 1000.0
            if row.moving_time_s:
                a["moving_h"] += row.moving_time_s / 3600.0
            if row.training_load:
                a["load"] += row.training_load
            if row.trimp:
                a["trimp"] += row.trimp
        out: list[dict] = []
        for week_start, a in sorted(agg.items()):
            a["week_start"] = week_start
            a["distance_km"] = round(a["distance_km"], 1)
            a["moving_h"] = round(a["moving_h"], 2)
            a["load"] = round(a["load"], 1)
            a["trimp"] = round(a["trimp"], 1)
            out.append(a)
        return out

    # ---------- 按日聚合（日历热力） ----------
    def day_aggregate(self, oldest: str, newest: str) -> list[dict]:
        rows = self._rows(oldest, newest)
        days: dict[str, dict] = defaultdict(
            lambda: {"date": "", "activities": 0, "load": 0.0, "distance_km": 0.0, "moving_min": 0}
        )
        for row in rows:
            d = _local_date(row.start_date_local)
            if d is None:
                continue
            a = days[d.isoformat()]
            a["date"] = d.isoformat()
            a["activities"] += 1
            if row.training_load:
                a["load"] += row.training_load
            if row.distance_m:
                a["distance_km"] += row.distance_m / 1000.0
            if row.moving_time_s:
                a["moving_min"] += round(row.moving_time_s / 60)
        out = []
        for a in days.values():
            a["load"] = round(a["load"], 1)
            a["distance_km"] = round(a["distance_km"], 1)
            out.append(a)
        return sorted(out, key=lambda x: x["date"])

    # ---------- 活动列表（倒序） ----------
    def activities(self, oldest: str, newest: str, limit: int = 200) -> dict:
        rows = list(reversed(self._rows(oldest, newest)))
        total = len(rows)
        items = [_activity_summary(row) for row in rows[:limit]]
        return {"total": total, "items": items}

    # ---------- 概览 ----------
    def overview(self, days: int = 90) -> dict:
        newest = local_today()
        oldest = newest - timedelta(days=days)
        smooth = self.fitness_series(oldest.isoformat(), newest.isoformat(), "smooth")
        points = self.fitness_series(oldest.isoformat(), newest.isoformat(), "points")
        weeks = self.weekly(oldest.isoformat(), newest.isoformat())
        return {
            "window": {"oldest": oldest.isoformat(), "newest": newest.isoformat()},
            "workout_days": len(points),
            "weekly": weeks,
            "current": smooth[-1] if smooth else None,
            "summary": {
                "activities": sum(w["activities"] for w in weeks),
                "distance_km": round(sum(w["distance_km"] for w in weeks), 1),
                "moving_h": round(sum(w["moving_h"] for w in weeks), 2),
                "load": round(sum(w["load"] for w in weeks), 1),
            },
        }


def _activity_summary(row: ActivityMirror) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "type": row.type,
        "start_date_local": row.start_date_local,
        "distance_km": round(row.distance_m / 1000.0, 1) if row.distance_m else None,
        "moving_min": int(row.moving_time_s / 60) if row.moving_time_s else None,
        "elevation_gain_m": row.elevation_gain_m,
        "average_heartrate": row.average_heartrate,
        "max_heartrate": row.max_heartrate,
        "average_cadence": row.average_cadence,
        "average_watts": row.average_watts,
        "weighted_avg_watts": row.weighted_avg_watts,
        "training_load": row.training_load,
        "trimp": row.trimp,
        "ctl": row.ctl,
        "atl": row.atl,
        "tsb": round(row.ctl - row.atl, 1)
        if row.ctl is not None and row.atl is not None
        else None,
        "trainer": row.trainer,
        "device_name": row.device_name,
    }


def _num(value: object) -> float | None:
    return float(value) if value is not None else None


def _local_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _next_day(value: str) -> str:
    d = date.fromisoformat(value) + timedelta(days=1)
    return f"{d.isoformat()}T00:00:00"


def _point(
    d: date,
    row: ActivityMirror | None,
    ctl: float | None = None,
    atl: float | None = None,
    *,
    include_load: bool = False,
) -> dict:
    if row is not None:
        ctl = _num(row.ctl) if ctl is None else ctl
        atl = _num(row.atl) if atl is None else atl
    out: dict = {
        "date": d.isoformat(),
        "ctl": round(ctl, 2) if ctl is not None else None,
        "atl": round(atl, 2) if atl is not None else None,
    }
    out["tsb"] = (
        round(out["ctl"] - out["atl"], 2)
        if out["ctl"] is not None and out["atl"] is not None
        else None
    )
    if include_load:
        out["load"] = _num(row.training_load) if row is not None else None
    return out
