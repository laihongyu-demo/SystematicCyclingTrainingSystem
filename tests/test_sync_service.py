"""同步服务幂等性测试（T2）：重复同步一致、变更检测、计数正确。"""
from __future__ import annotations

import httpx

from app.integrations.intervals.client import IntervalsClient
from app.models import ActivityMirror, Athlete, DailyFitness, DailyHealth, SyncLog
from app.services.sync_service import SyncService


def raw_act(aid: str, hr: int) -> dict:
    return {
        "id": aid,
        "name": f"Ride {aid}",
        "type": "Ride",
        "start_date_local": "2026-09-01T08:00:00",
        "start_date": "2026-09-01T00:00:00Z",
        "moving_time": 3600,
        "elapsed_time": 3700,
        "distance": 30000.0,
        "trainer": False,
        "device_watts": True,
        "has_heartrate": True,
        "average_heartrate": hr,
        "max_heartrate": 180,
        "icu_weighted_avg_watts": 180.0,
        "icu_training_load": 80,
        "file_type": "fit",
        "icu_athlete_id": "i93790",
        "icu_rolling_ftp": 127.0,
    }


def wellness_row(day: str, *, ctl: float | None = 30.0, atl: float | None = 40.0,
                 resting: float = 45.0, hrv: float = 50.0) -> dict:
    row = {"id": day, "ctl": ctl, "atl": atl, "restingHR": resting, "hrv": hrv}
    return row


def profile_payload() -> dict:
    return {
        "id": "i93790",
        "firstname": "T",
        "lastname": "U",
        "icu_weight": 51.0,
        "sportSettings": [
            {"types": ["Ride", "VirtualRide"], "ftp": 127, "indoor_ftp": None},
            {"types": ["Run"], "ftp": None},
        ],
    }


def client_for(
    items: list[dict],
    wellness: list[dict] | None = None,
    profile: dict | None = None,
) -> IntervalsClient:
    wellness = wellness if wellness is not None else []
    profile = profile if profile is not None else profile_payload()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "wellness" in url:
            return httpx.Response(200, json=wellness, request=request)
        if "activities" in url:
            return httpx.Response(200, json=items, request=request)
        if "/athlete/0" in url:
            return httpx.Response(200, json=profile, request=request)
        raise AssertionError(f"unexpected url: {url}")

    return IntervalsClient("test-key", transport=httpx.MockTransport(handler))


def test_idempotent_sync(session):
    items = [raw_act("a1", 140), raw_act("a2", 150)]
    client = client_for(items)
    svc = SyncService(session, client)

    r1 = svc.sync_activities("2026-06-01", "2026-09-05")
    assert (r1["inserted"], r1["updated"], r1["unchanged"]) == (2, 0, 0)

    r2 = svc.sync_activities("2026-06-01", "2026-09-05")
    assert (r2["inserted"], r2["updated"], r2["unchanged"]) == (0, 0, 2)

    assert session.query(ActivityMirror).count() == 2
    logs = session.query(SyncLog).order_by(SyncLog.id).all()
    assert len(logs) == 2
    assert all(log.status == "success" for log in logs)


def test_update_detection_on_metric_change(session):
    svc = SyncService(session, client_for([raw_act("a1", 140)]))
    svc.sync_activities("2026-06-01", "2026-09-05")

    svc = SyncService(session, client_for([raw_act("a1", 165)]))
    r = svc.sync_activities("2026-06-01", "2026-09-05")
    assert (r["inserted"], r["updated"], r["unchanged"]) == (0, 1, 0)

    row = session.get(ActivityMirror, "a1")
    assert row.average_heartrate == 165
    assert row.rolling_ftp == 127.0


def test_failed_sync_records_error_log(session):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="bad gateway", request=request)

    svc = SyncService(session, IntervalsClient("k", transport=httpx.MockTransport(handler)))
    try:
        svc.sync_activities("2026-06-01", "2026-09-05")
    except Exception:  # noqa: BLE001
        pass
    log = session.query(SyncLog).order_by(SyncLog.id.desc()).first()
    assert log is not None
    assert log.status == "failed"
    assert log.error


def test_wellness_mirrors_fitness_and_health(session):
    """M2.5：同一 wellness 请求同时写 daily_fitness 与 daily_health，二次同步幂等。"""
    wellness = [
        wellness_row("2026-09-01", ctl=30.0, atl=40.0, resting=43.0, hrv=36.86),
        wellness_row("2026-09-02", ctl=31.0, atl=38.0, resting=44.0, hrv=35.0),
    ]
    client = client_for([raw_act("a1", 140)], wellness=wellness)
    svc = SyncService(session, client)

    r1 = svc.sync_activities("2026-06-01", "2026-09-05")
    assert r1["wellness"]["fitness"] == {"inserted": 2, "updated": 0}
    assert r1["wellness"]["health"] == {"inserted": 2, "updated": 0}

    fit = {f.date: f for f in session.query(DailyFitness).all()}
    assert fit["2026-09-01"].ctl == 30.0 and fit["2026-09-02"].atl == 38.0

    health = {h.date: h for h in session.query(DailyHealth).all()}
    assert health["2026-09-01"].resting_rhr == 43.0
    assert health["2026-09-01"].hrv == 36.86

    # 二次同步：值未变，全部 unchanged（无 inserted/updated）
    r2 = svc.sync_activities("2026-06-01", "2026-09-05")
    assert r2["wellness"]["fitness"] == {"inserted": 0, "updated": 0}
    assert r2["wellness"]["health"] == {"inserted": 0, "updated": 0}


def test_wellness_value_change_triggers_update(session):
    """健康字段变化：同步后 daily_health 对应日更新。"""
    w1 = [wellness_row("2026-09-01", resting=43.0)]
    w2 = [wellness_row("2026-09-01", resting=48.0)]

    svc = SyncService(session, client_for([], wellness=w1))
    svc.sync_activities("2026-06-01", "2026-09-05")
    svc = SyncService(session, client_for([], wellness=w2))
    r = svc.sync_activities("2026-06-01", "2026-09-05")
    assert r["wellness"]["health"] == {"inserted": 0, "updated": 1}
    assert session.get(DailyHealth, "2026-09-01").resting_rhr == 48.0


def test_athlete_profile_mirrored(session):
    """M2.5：同步同时把 athlete 档案（FTP 设置）写入 athlete 表。"""
    svc = SyncService(session, client_for([raw_act("a1", 140)]))
    svc.sync_activities("2026-06-01", "2026-09-05")
    athlete = session.get(Athlete, "i93790")
    assert athlete is not None
    assert athlete.weight == 51.0
    assert '"ftp": 127' in athlete.sport_settings_json
