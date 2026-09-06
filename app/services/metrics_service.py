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

import json
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ActivityMirror,
    Athlete,
    DailyFitness,
    DailyHealth,
    MorningRhr,
)
from app.utils.dates import local_today

CTL_TAU_DAYS = 42.0
ATL_TAU_DAYS = 7.0

# 骑行运动类型集合：capability(eFTP) 与能力卡相关口径均以骑行运动为准
RIDE_TYPES = ("Ride", "VirtualRide", "MountainBikeRide", "GravelRide")


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

    # ---------- 能力指标（M2.5 FR-2.1.2） ----------
    def capability(self) -> dict:
        """FTP / eFTP / w·kg⁻¹ 能力指标（含口径与取数时间）。

        - FTP：intervals 档案 sportSettings 中骑行运动（Ride/VirtualRide…）的 ftp 设置；
        - eFTP：intervals 官方滚动估算（icu_rolling_ftp），取最近一次骑行活动快照，
          无则返回 None（前端显示「—」，注明未提供）；
        - w/kg：FTP ÷ 体重；体重优先取最新 wellness 日值（daily_health），
          无 wellness 时退回档案快照，并回传来源与日期。
        """
        athlete = self._session.scalars(
            select(Athlete).order_by(Athlete.last_synced_at.desc()).limit(1)
        ).first()
        ftp = None
        ftp_synced = None
        if athlete is not None:
            ftp = _cycling_ftp(athlete.sport_settings_json)
            ftp_synced = _local_date_str(athlete.last_synced_at)

        # eFTP：最近一次骑行活动的 icu_rolling_ftp
        eftp = eftp_date = None
        latest = self._session.scalars(
            select(ActivityMirror)
            .where(
                ActivityMirror.type.in_(RIDE_TYPES),
                ActivityMirror.rolling_ftp.is_not(None),
            )
            .order_by(ActivityMirror.start_date_local.desc())
            .limit(1)
        ).first()
        if latest is not None:
            eftp = round(latest.rolling_ftp, 1)
            eftp_date = (latest.start_date_local or "")[:10] or None

        # 体重：最新 wellness 日值优先，其次档案快照
        weight = None
        weight_source = None
        weight_date = None
        health_row = self._session.scalars(
            select(DailyHealth)
            .where(DailyHealth.weight.is_not(None))
            .order_by(DailyHealth.date.desc())
            .limit(1)
        ).first()
        if health_row is not None:
            weight = round(health_row.weight, 1)
            weight_source = "wellness"
            weight_date = health_row.date
        elif athlete is not None and athlete.weight is not None:
            weight = round(athlete.weight, 1)
            weight_source = "athlete_profile"
            weight_date = ftp_synced

        wkg = round(ftp / weight, 2) if ftp is not None and weight else None
        return {
            "ftp": ftp,
            "ftp_synced": ftp_synced,
            "eftp": eftp,
            "eftp_date": eftp_date,
            "weight_kg": weight,
            "weight_source": weight_source,
            "weight_date": weight_date,
            "w_per_kg": wkg,
        }

    # ---------- 健康日序列（M2.5 FR-2.1.3，按天粒度） ----------
    def health_daily(self, oldest: str, newest: str) -> dict:
        """健康看板天粒度数据：窗口内逐日（缺口日置空，标注 covered）。

        字段为 M2.5-1 spike 实测的 wellness 镜像：RHR / HRV / HRV_SDNN / 体重 / 体脂。
        """
        rows = self._session.scalars(
            select(DailyHealth)
            .where(DailyHealth.date >= oldest, DailyHealth.date <= newest)
            .order_by(DailyHealth.date)
        ).all()
        by_day = {r.date: r for r in rows}
        start = date.fromisoformat(oldest)
        end = date.fromisoformat(newest)
        days: list[dict] = []
        covered = 0
        cursor = start
        while cursor <= end:
            day = cursor.isoformat()
            row = by_day.get(day)
            has = row is not None and any(
                getattr(row, col) is not None
                for col in ("resting_rhr", "hrv", "hrv_sdnn", "weight", "fat_percent")
            )
            if has:
                covered += 1
            days.append(
                {
                    "date": day,
                    "has_data": has,
                    "resting_rhr": _num(row.resting_rhr) if has else None,
                    "hrv": _num(row.hrv) if has else None,
                    "hrv_sdnn": _num(row.hrv_sdnn) if has else None,
                    "weight": _num(row.weight) if has else None,
                    "fat_percent": _num(row.fat_percent) if has else None,
                }
            )
            cursor += timedelta(days=1)
        return {
            "window": {"oldest": oldest, "newest": newest},
            "covered_days": covered,
            "days": days,
        }

    # ---------- 晨起 RHR（M2.5 FR-2.1.4，手动录入） ----------
    def morning_rhr_series(self, oldest: str, newest: str) -> dict:
        """晨起 RHR 记录（按天 1 条）。delta 只与“日历上一天”的记录比较，
        无昨日数据则 delta 为 None（前端标注「无昨日数据」，不误报 0）。"""
        rows = self._session.scalars(
            select(MorningRhr)
            .where(MorningRhr.date >= oldest, MorningRhr.date <= newest)
            .order_by(MorningRhr.date)
        ).all()
        by_day = {r.date: r for r in rows}
        items: list[dict] = []
        for r in rows:
            prev = by_day.get((date.fromisoformat(r.date) - timedelta(days=1)).isoformat())
            items.append(
                {
                    "date": r.date,
                    "value": r.value,
                    "note": r.note,
                    "source": r.source,
                    "updated_at": _fmt_utc(r.updated_at),
                    "prev_date": prev.date if prev else None,
                    "delta": round(r.value - prev.value, 1) if prev else None,
                }
            )
        return {"window": {"oldest": oldest, "newest": newest}, "items": items}

    def morning_rhr_upsert(
        self,
        day: str,
        value: float,
        note: str | None = None,
        *,
        overwrite: bool = False,
    ) -> dict:
        """按天写入/覆盖晨起 RHR；同天已有且未显式 overwrite 时返回 conflict。

        返回值 status ∈ created | updated | conflict。
        """
        existing = self._session.get(MorningRhr, day)
        if existing is not None and not overwrite:
            return {
                "status": "conflict",
                "existing": {"date": existing.date, "value": existing.value},
            }
        if existing is None:
            self._session.add(MorningRhr(date=day, value=value, note=note))
            status = "created"
        else:
            existing.value = value
            existing.note = note
            status = "updated"
        self._session.commit()
        return {"status": status, "date": day}

    def morning_rhr_delete(self, day: str) -> bool:
        row = self._session.get(MorningRhr, day)
        if row is None:
            return False
        self._session.delete(row)
        self._session.commit()
        return True

    # ---------- LLM 数据源白名单（M2.5-6 / FR-3.4，供 M3 上下文构建器） ----------
    def context_snapshot(self, days: int = 30) -> dict:
        """把指标+健康以“天粒度、有界字段白名单”聚合，供 M3 上下文构建器注入。

        - 体能：窗口内官方 CTL/ATL/TSB 平滑曲线（截取每日值）＋当前值；
        - 健康：窗口内 RHR/HRV/体重（缺口标注，无插值）；
        - 晨起 RHR 最近条目；能力指标取档（FTP/eFTP/w·kg⁻¹）。
        """
        newest = local_today()
        oldest = newest - timedelta(days=days - 1)
        lo, hi = oldest.isoformat(), newest.isoformat()

        smooth = self.fitness_series(lo, hi, "smooth")
        current = smooth[-1] if smooth else None

        health = self.health_daily(lo, hi)
        morning = self.morning_rhr_series(lo, hi)

        return {
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "window": {"oldest": lo, "newest": hi},
            "current_fitness": current,
            "capability": self.capability(),
            "health_days": health["days"],
            "health_covered_days": health["covered_days"],
            "morning_rhr": morning["items"],
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


def _cycling_ftp(sport_settings_json: str | None) -> float | None:
    """从 athlete 档案 sportSettings 提取骑行 FTP 设置。

    intervals.icu 的 sportSettings 每项含 types 列表（如 ['Ride','VirtualRide']）
    与 ftp/indoor_ftp；骑行运动设置里的 ftp 即指标卡口径。异常 JSON 或缺骑行项返回 None。
    """
    if not sport_settings_json:
        return None
    try:
        items = json.loads(sport_settings_json)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        types = item.get("types") or []
        if isinstance(types, list) and any(t in RIDE_TYPES for t in types):
            return _num(item.get("ftp"))
    # 无 types 匹配时退回首个数字型 ftp
    for item in items:
        if isinstance(item, dict) and item.get("ftp") is not None:
            return _num(item["ftp"])
    return None


def _local_date_str(value: datetime | None) -> str | None:
    """把存储时间戳按运动员本地时区（UTC+8）转成 YYYY-MM-DD。"""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return (value + timedelta(hours=8)).strftime("%Y-%m-%d")


def _fmt_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


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
