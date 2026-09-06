"""活动契约映射测试（T1/T2）。"""
from __future__ import annotations

from app.integrations.intervals.mapping import map_activity

SAMPLE = {
    "id": "i183491745",
    "name": "CP20",
    "type": "VirtualRide",
    "start_date_local": "2026-09-05T15:17:41",
    "start_date": "2026-09-05T07:17:41Z",
    "moving_time": 3006,
    "elapsed_time": 3006,
    "distance": 18039.3,
    "total_elevation_gain": None,
    "trainer": True,
    "device_name": "Garmin Edge 540",
    "device_watts": True,
    "has_heartrate": True,
    "average_heartrate": 144,
    "max_heartrate": 176,
    "average_cadence": 91.40818,
    "icu_weighted_avg_watts": 110,
    "max_speed": 8.052,
    "average_speed": 6.001,
    "calories": 351,
    "trimp": 60.611107,
    "icu_training_load": 70,
    "icu_atl": 36.572548,
    "icu_ctl": 22.572884,
    "perceived_exertion": None,
    "external_id": "24243189781",
    "file_type": "fit",
    "icu_athlete_id": "i93790",
    # 易变/无关字段不应影响 content_hash
    "icu_sync_date": "2026-09-05T08:10:30.519+00:00",
    "gear": {"id": "10027", "name": None},
}


def test_map_activity_columns():
    row = map_activity(SAMPLE)
    assert row["id"] == "i183491745"
    assert row["athlete_id"] == "i93790"
    assert row["moving_time_s"] == 3006
    assert row["distance_m"] == 18039.3
    assert row["trainer"] is True
    assert row["has_heartrate"] is True
    assert row["weighted_avg_watts"] == 110
    assert row["trimp"] == 60.611107
    assert row["elevation_gain_m"] is None
    assert row["perceived_exertion"] is None
    assert '"name": "CP20"' in row["raw_json"]


def test_map_content_hash_ignores_volatile_fields():
    row1 = map_activity(SAMPLE)
    mutated = dict(SAMPLE)
    mutated["icu_sync_date"] = "2026-09-06T00:00:00.000+00:00"
    mutated["created"] = "2026-09-06T00:00:00"
    row2 = map_activity(mutated)
    assert row1["content_hash"] == row2["content_hash"]


def test_map_content_hash_changes_on_metric_change():
    row1 = map_activity(SAMPLE)
    mutated = dict(SAMPLE)
    mutated["average_heartrate"] = 160
    row2 = map_activity(mutated)
    assert row1["content_hash"] != row2["content_hash"]
