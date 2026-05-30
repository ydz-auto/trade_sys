"""
Domain Persistence Base - SQLAlchemy DeclarativeBase

供 domain 层 ORM 模型继承使用。
infrastructure 层的 SQLAlchemyManager 也从此处导入 Base。
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
