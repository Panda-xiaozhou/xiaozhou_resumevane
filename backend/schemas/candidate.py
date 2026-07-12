"""
候选人端 API 的 Pydantic 模型
==============================
定义简历投递和状态查询的请求和响应格式。
"""
from pydantic import BaseModel, Field, EmailStr


class CandidateApplyRequest(BaseModel):
    """投递表单请求（用于文档生成，实际接口使用 Form 上传文件）"""
    name: str = Field(..., min_length=1, max_length=64, description="姓名")
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$', description="邮箱")
    phone: str = Field(default="", max_length=32, description="手机号")
    job_id: str = Field(..., description="投递的岗位 ID")
    self_intro: str = Field(default="", max_length=2000, description="自我介绍")
    expected_salary: str = Field(default="", max_length=32, description="期望薪资")


class CandidateApplicationResponse(BaseModel):
    """候选人投递历史项"""
    id: str
    job_id: str
    status: str
    match_score: float
    created_at: str
