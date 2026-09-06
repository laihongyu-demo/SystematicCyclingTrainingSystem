"""运动员本地时间口径（中国时区 UTC+8，无夏令时）。

本地单机工具面向中国时区用户；所有“今天/窗口边界/活动本地时间”均以此为准。
同步日志等内部时间戳仍以 UTC 存储（模型默认），仅展示层换算。
用固定偏移实现，避免 Windows 下 zoneinfo/tzdata 缺失导致运行时报错。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

# Asia/Shanghai 无夏令时，全年固定 UTC+8
ATHLETE_UTC_OFFSET = timedelta(hours=8)


def local_today() -> date:
    """运动员所在时区的“今天”日期。"""
    return (datetime.now(timezone.utc) + ATHLETE_UTC_OFFSET).date()
