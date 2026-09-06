"""同步服务幂等性测试（T2）：重复同步一致、变更检测、计数正确。"""
from __future__ import annotations

import httpx

from app.integrations.intervals.client import IntervalsClient
from app.models import ActivityMirror, SyncLog
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
    }


def client_for(items: list[dict]) -> IntervalsClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "activities" in str(request.url)
        return httpx.Response(200, json=items, request=request)

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
