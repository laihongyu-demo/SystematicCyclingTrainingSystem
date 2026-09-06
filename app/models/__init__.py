"""ORM 模型注册（导入即被 SQLAlchemy 元数据收集）。"""
from app.models.credential import Credential

__all__ = ["Credential"]
