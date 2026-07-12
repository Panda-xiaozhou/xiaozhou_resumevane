"""
用户模型：HR 管理员 + 候选人
============================
HR 用户通过后台登录后管理岗位和查看筛选结果。
候选人信息在投递时自动创建（以邮箱为唯一标识去重）。
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class HrUser(Base):
    """
    HR 管理员用户表
    ┌──────────────┬──────────────────────┐
    │ 字段          │ 说明                  │
    ├──────────────┼──────────────────────┤
    │ id           │ 主键，UUID            │
    │ username     │ 登录用户名，唯一       │
    │ password_hash│ bcrypt 哈希后的密码    │
    │ display_name │ 显示名称              │
    │ feishu_open_id│ 飞书用户 ID（可选）   │
    └──────────────┴──────────────────────┘
    """
    __tablename__ = "hr_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    display_name = Column(String(64), nullable=False)
    # 飞书 open_id 用于定向推送消息给特定 HR，为空时推到群聊
    feishu_open_id = Column(String(128), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Candidate(Base):
    """
    候选人表
    ┌──────────┬────────────────────┐
    │ 字段      │ 说明               │
    ├──────────┼────────────────────┤
    │ id       │ 主键，UUID          │
    │ name     │ 候选人姓名          │
    │ email    │ 邮箱（去重标识）     │
    │ phone    │ 手机号（可选）       │
    └──────────┴────────────────────┘
    注意：同一邮箱多次投递不会重复创建候选人记录
    """
    __tablename__ = "candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(64), nullable=False)
    email = Column(String(128), nullable=False, index=True)
    phone = Column(String(32), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
