"""
投递记录模型
============
候选人每次投递对应一条 Application 记录。
投递后触发 Agent 流水线，状态流转：
  pending → processing → passed / pending_review / rejected
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB

from .base import Base


class Application(Base):
    """
    投递记录表 — 系统核心业务表
    ┌──────────────┬──────────────────────────────────────┐
    │ 字段          │ 说明                                  │
    ├──────────────┼──────────────────────────────────────┤
    │ id           │ 主键，UUID                            │
    │ candidate_id │ 候选人 ID（关联 candidates 表）        │
    │ job_id       │ 岗位 ID（关联 jobs 表）               │
    │ resume_file  │ 简历文件在服务器上的存储路径            │
    │ form_data    │ 候选人填写的表单信息（JSONB）           │
    │ status       │ 筛选状态（见下方状态机）               │
    │ match_score  │ Agent 匹配打分（0-100）               │
    │ push_status  │ 飞书推送状态                          │
    └──────────────┴──────────────────────────────────────┘

    状态机流转：
    pending ──(触发流水线)──→ processing ──(Agent 决策)──→ passed     (推荐，触发飞书推送)
                                                         ├→ pending_review (待定，HR 人工看板)
                                                         └→ rejected   (不推荐，归档)

    推送状态：
    none ──→ pushing ──→ pushed   (推送成功)
                     └─→ failed   (推送失败，HR 看板可重试)
    """
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id"), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False, index=True)
    resume_file = Column(String(512), default="")
    # form_data 示例: {"self_intro": "...", "expected_salary": "15K-20K"}
    form_data = Column(JSONB, default=dict)
    status = Column(String(16), default="pending", index=True)
    match_score = Column(Float, default=0.0)
    push_status = Column(String(16), default="none")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
