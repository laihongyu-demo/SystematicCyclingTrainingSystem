"""intervals.icu 活动契约 -> 镜像表字段映射（单一事实源）。

- 字段裁剪：镜像只保留设计与统计需要的核心列，其余保留在 raw_json 快照；
- content_hash：对“非易变核心字段”做 sha1，用于幂等同步与变更检测
  （易变字段如 icu_sync_date/created/analyzed 不参与，避免无意义“更新”）。
"""
from __future__ import annotations

import hashlib
import json

# 列名 -> intervals.icu 原始 JSON 字段名
SOURCE_FIELDS: dict[str, str] = {
    "id": "id",
    "athlete_id": "icu_athlete_id",
    "name": "name",
    "type": "type",
    "start_date_local": "start_date_local",
    "start_date_utc": "start_date",
    "moving_time_s": "moving_time",
    "elapsed_time_s": "elapsed_time",
    "distance_m": "distance",
    "elevation_gain_m": "total_elevation_gain",
    "trainer": "trainer",
    "device_name": "device_name",
    "device_watts": "device_watts",
    "has_heartrate": "has_heartrate",
    "average_heartrate": "average_heartrate",
    "max_heartrate": "max_heartrate",
    "average_cadence": "average_cadence",
    "average_watts": "icu_average_watts",
    "weighted_avg_watts": "icu_weighted_avg_watts",
    "max_speed": "max_speed",
    "average_speed": "average_speed",
    "calories": "calories",
    "trimp": "trimp",
    "training_load": "icu_training_load",
    "atl": "icu_atl",
    "ctl": "icu_ctl",
    "perceived_exertion": "perceived_exertion",
    "external_id": "external_id",
    "file_type": "file_type",
}

_BOOL_KEYS = {"trainer", "device_watts", "has_heartrate"}


def map_activity(raw: dict) -> dict:
    """把一条 activity JSON 映射为 activity_mirror 行数据（含 content_hash）。"""
    core: dict = {}
    for column, source_key in SOURCE_FIELDS.items():
        value = raw.get(source_key)
        if column in _BOOL_KEYS:
            value = bool(value)
        elif isinstance(value, str):
            value = value.strip() or None
        core[column] = value

    core["raw_json"] = json.dumps(raw, ensure_ascii=False, sort_keys=True)
    payload = {k: v for k, v in core.items() if k != "raw_json"}
    content_hash = hashlib.sha1(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()
    ).hexdigest()
    core["content_hash"] = content_hash
    return core
