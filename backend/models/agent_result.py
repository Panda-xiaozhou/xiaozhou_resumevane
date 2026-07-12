"""
Agent 结果模型
==============
记录 Agent 流水线每一步的中间输出，用于：
  1. 面试时展示 Agent 内部分析过程
  2. 问题排查（哪个 Agent 节点出错、输出什么）
  3. 评测分析（对比 Agent 输出 vs 人工标注）
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB

from .base import Base


class AgentResult(Base):
    """
    Agent 执行结果表
    ┌────────────────┬──────────────────────────────────────┐
    │ 字段            │ 说明                                  │
    ├────────────────┼──────────────────────────────────────┤
    │ id             │ 主键，UUID                            │
    │ application_id │ 关联的投递记录                        │
    │ agent_name     │ 节点名称（orchestrator/parser/matcher/ │
    │                │  analyzer/reporter/approver/pipeline） │
    │ status         │ pending/running/completed/failed       │
    │ output_data    │ 结构化输出 JSON                        │
    │ error_message  │ 错误信息（如有）                       │
    └────────────────┴──────────────────────────────────────┘

    output_data 示例（pipeline 汇总记录）：
    {
        "match_score": 85,
        "dimension_scores": {"hard_skill": 90, "education": 80, ...},
        "matched_keywords": ["Python", "React"],
        "missing_keywords": ["Docker"],
        "highlights": [{"type": "开源贡献", "detail": "..."}],
        "risks": [],
        "overall_flag": "green",
        "recommend": "推荐",
        "decision_reason": "匹配度 85 分，综合评级绿色，自动通过",
        "report_markdown": "## 候选人筛选报告\n..."
    }
    """
    __tablename__ = "agent_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(
        UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False, index=True
    )
    agent_name = Column(String(32), nullable=False)
    status = Column(String(16), default="pending")
    # output_data 存储各 Agent 的结构化输出，JSONB 支持灵活的查询
    output_data = Column(JSONB, default=dict)
    error_message = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
