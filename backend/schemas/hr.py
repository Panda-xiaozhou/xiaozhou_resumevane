"""
HR 后台 API 的 Pydantic 模型
==============================
定义 HR 注册、登录、岗位管理、投递管理的请求和响应格式。
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, EmailStr


# ── 认证 ────────────────────────────────────────────

class HrRegisterRequest(BaseModel):
    """HR 注册请求"""
    username: str = Field(..., min_length=3, max_length=64, description="登录用户名")
    password: str = Field(..., min_length=6, max_length=128, description="登录密码")
    display_name: str = Field(..., min_length=1, max_length=64, description="显示名称")


class HrLoginRequest(BaseModel):
    """HR 登录请求"""
    username: str = Field(..., min_length=1, max_length=64, description="登录用户名")
    password: str = Field(..., min_length=1, max_length=128, description="登录密码")


class HrTokenResponse(BaseModel):
    """HR 登录响应"""
    token: str
    user_id: str
    display_name: str


# ── 岗位管理 ────────────────────────────────────────

class JobCreateRequest(BaseModel):
    """创建岗位请求"""
    title: str = Field(..., min_length=1, max_length=128, description="岗位名称")
    department: str = Field(default="", max_length=64, description="部门名称")
    jd_text: str = Field(..., min_length=10, description="岗位描述（至少 10 个字符）")
    jd_keywords: str = Field(default="", description="关键技能词（逗号分隔），如 Python,FastAPI,React")


class JobResponse(BaseModel):
    """岗位列表响应"""
    id: str
    title: str
    department: str
    status: str
    jd_keywords: list[str]
    created_at: str


# ── 投递管理 ────────────────────────────────────────

class ApplicationResponse(BaseModel):
    """投递列表项"""
    id: str
    candidate_id: str
    status: str
    match_score: float
    push_status: str
    created_at: str


class AgentResultData(BaseModel):
    """Agent 分析结果"""
    match_score: float = 0
    dimension_scores: dict[str, float] = {}
    matched_keywords: list[str] = []
    missing_keywords: list[str] = []
    highlights: list[dict] = []
    risks: list[dict] = []
    overall_flag: str = "yellow"
    recommend: str = "待定"
    decision_reason: str = ""
    report_markdown: str = ""


class ApplicationDetailResponse(BaseModel):
    """投递详情（含 Agent 分析结果）"""
    id: str
    status: str
    match_score: float
    push_status: str
    form_data: dict[str, Any]
    agent_result: AgentResultData


# ── 通用分页 ────────────────────────────────────────

class PaginatedResponse(BaseModel):
    """通用分页响应"""
    total: int
    page: int
    page_size: int
    items: list[Any]
