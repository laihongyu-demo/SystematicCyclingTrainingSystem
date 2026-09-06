"""健康中心服务测试（M2.5）：capability 口径、天粒度补缺、晨起 RHR 冲突与昨日差。"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from app.models import ActivityMirror, Athlete, DailyHealth
from app.services.metrics_service import MetricsService


def _athlete(ftp: float | None = 250.0) -> Athlete:
    return Athlete(
        remote_id="i93790",
        display_name="T U",
        weight=70.0,
        last_synced_at=datetime.now(UTC),
        sport_settings_json=json.dumps(
            [
                {"types": ["Ride", "VirtualRide"], "ftp": ftp, "indoor_ftp": None},
                {"types": ["Run"], "ftp": None},
            ]
        ),
    )


def _ride(aid: str, when: str, rolling_ftp: float | None) -> ActivityMirror:
    return ActivityMirror(
        id=aid,
        type="Ride",
        start_date_local=when,
        start_date_utc=when,
        rolling_ftp=rolling_ftp,
        raw_json="{}",
        content_hash="h",
    )


def _health(day: str, *, resting: float | None = None, weight: float | None = None) -> DailyHealth:
    return DailyHealth(date=day, resting_rhr=resting, weight=weight)


def test_capability_uses_athlete_ftp_latest_eftp_and_wellness_weight(session):
    session.add_all(
        [
            _athlete(ftp=250),
            _ride("a1", "2026-09-03T08:00:00", 245.0),
            _ride("a2", "2026-09-05T08:00:00", 248.0),  # 最新一次
            _health("2026-09-05", weight=70.0),
        ]
    )
    session.commit()
    cap = MetricsService(session).capability()
    assert cap["ftp"] == 250.0
    assert cap["eftp"] == 248.0
    assert cap["eftp_date"] == "2026-09-05"
    assert cap["weight_kg"] == 70.0
    assert cap["weight_source"] == "wellness"
    assert cap["w_per_kg"] == round(250.0 / 70.0, 2)


def test_capability_empty_when_no_sync(session):
    cap = MetricsService(session).capability()
    assert cap["ftp"] is None and cap["eftp"] is None and cap["w_per_kg"] is None


def test_capability_eftp_none_when_no_riding_rolling_ftp(session):
    session.add_all([_athlete(), _ride("a1", "2026-09-03T08:00:00", None)])
    session.commit()
    cap = MetricsService(session).capability()
    assert cap["ftp"] == 250.0
    assert cap["eftp"] is None
    # 无 wellness 体重时退回档案快照（athlete.weight=70）
    assert cap["weight_source"] == "athlete_profile"
    assert cap["w_per_kg"] == round(250.0 / 70.0, 2)


def test_health_daily_marks_gaps(session):
    session.add_all([_health("2026-09-01", resting=45.0), _health("2026-09-03", resting=44.0)])
    session.commit()
    out = MetricsService(session).health_daily("2026-09-01", "2026-09-03")
    days = out["days"]
    assert [d["date"] for d in days] == ["2026-09-01", "2026-09-02", "2026-09-03"]
    assert days[0]["has_data"] is True and days[0]["resting_rhr"] == 45.0
    assert days[1]["has_data"] is False  # 缺口日置空
    assert days[2]["has_data"] is True
    assert out["covered_days"] == 2


def test_morning_rhr_delta_only_against_calendar_yesterday(session):
    from app.models import MorningRhr

    session.add_all(
        [
            MorningRhr(date="2026-09-01", value=46.0),
            MorningRhr(date="2026-09-03", value=44.0),  # 昨日(09-02)无记录
        ]
    )
    session.commit()
    out = MetricsService(session).morning_rhr_series("2026-09-01", "2026-09-03")
    first, third = out["items"]
    assert first["delta"] is None
    assert third["delta"] is None  # 不误报为 0/-2
    assert third["prev_date"] is None


def test_morning_rhr_delta_with_consecutive_days(session):
    from app.models import MorningRhr

    session.add_all(
        [
            MorningRhr(date="2026-09-01", value=46.0),
            MorningRhr(date="2026-09-02", value=48.0),
        ]
    )
    session.commit()
    items = MetricsService(session).morning_rhr_series("2026-09-01", "2026-09-02")["items"]
    assert items[1]["delta"] == 2.0
    assert items[1]["prev_date"] == "2026-09-01"


def test_morning_rhr_conflict_requires_overwrite(session):
    from app.models import MorningRhr

    svc = MetricsService(session)
    session.add(MorningRhr(date="2026-09-01", value=46.0))
    session.commit()

    assert svc.morning_rhr_upsert("2026-09-01", 50.0)["status"] == "conflict"
    assert svc.morning_rhr_upsert("2026-09-01", 50.0, overwrite=True)["status"] == "updated"
    assert svc.morning_rhr_upsert("2026-09-02", 49.0)["status"] == "created"

    assert svc.morning_rhr_delete("2026-09-02") is True
    assert svc.morning_rhr_delete("2026-09-02") is False
