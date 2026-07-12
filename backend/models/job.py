"""
岗位模型：HR 创建和管理招聘岗位
==============================
每个岗位包含 JD 文本、关键技能词、匹配权重配置，
这些信息会被 Agent 流水线读取用于匹配打分。
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

from .base import Base


class Job(Base):
    """
    岗位表
    ┌──────────────┬──────────────────────────────────────┐
    │ 字段          │ 说明                                  │
    ├──────────────┼──────────────────────────────────────┤
    │ id           │ 主键，UUID                            │
    │ hr_user_id   │ 创建该岗位的 HR 用户 ID               │
    │ title        │ 岗位名称（如"前端开发工程师"）          │
    │ department   │ 部门名称                              │
    │ jd_text      │ JD 完整文本（Agent 匹配时使用）        │
    │ jd_keywords  │ 关键技能词数组（如["Python","React"]） │
    │ match_config │ 匹配权重配置 JSON                     │
    │ status       │ 状态: draft(草稿)/published(发布)/closed(关闭) │
    └──────────────┴──────────────────────────────────────┘

    match_config 示例：
    {
        "hard_skill": 0.40,    // 硬技能权重 40%
        "education": 0.20,     // 学历权重 20%
        "experience": 0.25,    // 经验权重 25%
        "project": 0.15        // 项目权重 15%
    }
    """
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hr_user_id = Column(UUID(as_uuid=True), ForeignKey("hr_users.id"), nullable=False, index=True)
    title = Column(String(128), nullable=False)
    department = Column(String(64), default="")
    # jd_text 存储完整 JD，LLM 匹配时会被截取前 3000 字符
    jd_text = Column(Text, nullable=False)
    # jd_keywords 用于向量检索 + 关键词命中率计算
    jd_keywords = Column(ARRAY(String), default=[])
    # match_config 允许 HR 自定义各维度的评分权重
    match_config = Column(JSONB, default=dict)
    status = Column(String(16), default="draft", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
