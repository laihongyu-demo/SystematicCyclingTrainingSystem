"""指标汇总层测试（T2）：周负荷、体能曲线锚点零误差、平滑衰减、同日取末次快照。"""
from __future__ import annotations

import math

from app.models import ActivityMirror
from app.services.metrics_service import MetricsService


def _act(
    aid: str,
    when: str,
    *,
    ctl: float,
    atl: float,
    load: float | None = None,
    distance_m: float = 0.0,
    moving_time_s: int = 0,
    trimp: float = 0.0,
) -> ActivityMirror:
    return ActivityMirror(
        id=aid,
        athlete_id="i93790",
        name=f"A{aid}",
        type="Ride",
        start_date_local=when,
        start_date_utc=when.replace("T", "T"),
        distance_m=distance_m,
        moving_time_s=moving_time_s,
        ctl=ctl,
        atl=atl,
        training_load=load,
        trimp=trimp,
        raw_json="{}",
        content_hash="h",
    )


def test_points_equal_official_snapshots(session):
    svc = MetricsService(session)
    session.add_all(
        [
            _act(
                "a1",
                "2026-09-07T08:00:00",
                ctl=30.0,
                atl=40.0,
                load=50.0,
                distance_m=20000.0,
                moving_time_s=3600,
                trimp=30.0,
            ),
            _act(
                "a2",
                "2026-09-14T08:00:00",
                ctl=33.0,
                atl=50.0,
                load=70.0,
                distance_m=30000.0,
                moving_time_s=5400,
                trimp=45.0,
            ),
        ]
    )
    session.commit()

    pts = svc.fitness_series("2026-09-01", "2026-09-30", "points")
    assert [p["date"] for p in pts] == ["2026-09-07", "2026-09-14"]
    # 与 intervals.icu 官方快照零误差（G2 ±1% 前提）
    assert pts[0]["ctl"] == 30.0 and pts[0]["atl"] == 40.0 and pts[0]["tsb"] == -10.0
    assert pts[1]["ctl"] == 33.0 and pts[1]["atl"] == 50.0 and pts[1]["tsb"] == -17.0
    assert pts[1]["load"] == 70.0


def test_smooth_decay_between_workouts(session):
    svc = MetricsService(session)
    session.add(_act("a1", "2026-09-07T08:00:00", ctl=30.0, atl=40.0, load=50.0))
    session.commit()

    series = svc.fitness_series("2026-09-07", "2026-09-14", "smooth")
    assert len(series) == 8
    assert series[0]["date"] == "2026-09-07"
    assert series[0]["ctl"] == 30.0
    # 无活动日按 42/7 天 τ 指数衰减
    assert series[1]["ctl"] == round(30.0 * math.exp(-1 / 42), 2)
    assert series[1]["atl"] == round(40.0 * math.exp(-1 / 7), 2)


def test_same_day_keeps_latest_snapshot(session):
    svc = MetricsService(session)
    session.add_all(
        [
            _act("a1", "2026-09-07T08:00:00", ctl=29.0, atl=39.0, load=20.0),
            _act("a2", "2026-09-07T18:00:00", ctl=31.5, atl=44.0, load=60.0),
        ]
    )
    session.commit()
    pts = svc.fitness_series("2026-09-01", "2026-09-30", "points")
    assert len(pts) == 1
    assert pts[0]["ctl"] == 31.5 and pts[0]["atl"] == 44.0
    assert pts[0]["load"] == 60.0


def test_weekly_summary(session):
    svc = MetricsService(session)
    session.add_all(
        [
            _act(
                "a1",
                "2026-09-07T08:00:00",
                ctl=30.0,
                atl=40.0,
                load=50.0,
                distance_m=20000.0,
                moving_time_s=3600,
                trimp=30.0,
            ),
            _act(
                "a2",
                "2026-09-14T08:00:00",
                ctl=33.0,
                atl=50.0,
                load=70.0,
                distance_m=30000.0,
                moving_time_s=5400,
                trimp=45.0,
            ),
        ]
    )
    session.commit()
    weeks = svc.weekly("2026-09-01", "2026-09-30")
    assert [w["week_start"] for w in weeks] == ["2026-09-07", "2026-09-14"]
    w1, w2 = weeks
    assert w1["activities"] == 1 and w1["distance_km"] == 20.0 and w1["load"] == 50.0
    assert w1["moving_h"] == 1.0 and w1["trimp"] == 30.0
    assert w2["load"] == 70.0


def test_overview_current_is_last_smooth_point(session):
    svc = MetricsService(session)
    session.add(_act("a1", "2026-09-04T08:00:00", ctl=33.0, atl=50.0, load=70.0))
    session.commit()
    view = svc.overview(days=30)
    assert view["workout_days"] == 1
    # current 为推演到今日（窗口最新日）的平滑值：09-04 -> 今日按 CTL τ=42d 衰减
    assert view["current"]["ctl"] == round(33.0 * math.exp(-2 / 42.0), 2)
    assert view["summary"]["activities"] == 1
    assert view["summary"]["load"] == 70.0
