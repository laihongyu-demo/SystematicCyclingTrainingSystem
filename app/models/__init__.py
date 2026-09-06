"""ORM 模型注册（导入即被 SQLAlchemy 元数据收集）。"""
from app.models.activity_mirror import ActivityMirror
from app.models.athlete import Athlete
from app.models.credential import Credential
from app.models.daily_fitness import DailyFitness
from app.models.daily_health import DailyHealth
from app.models.morning_rhr import MorningRhr
from app.models.sync_log import SyncLog

__all__ = [
    "ActivityMirror",
    "Athlete",
    "Credential",
    "DailyFitness",
    "DailyHealth",
    "MorningRhr",
    "SyncLog",
]
