"""
Pydantic 请求/响应模型
======================
为所有 API 接口提供类型安全的输入校验和响应序列化。

使用这些 schema 后，FastAPI 会自动：
  - 校验请求体类型和格式
  - 生成完整的 OpenAPI 文档
  - 返回清晰的校验错误信息
"""
from .hr import (
    HrRegisterRequest,
    HrLoginRequest,
    HrTokenResponse,
    JobCreateRequest,
    JobResponse,
    ApplicationResponse,
    ApplicationDetailResponse,
    PaginatedResponse,
)
from .candidate import (
    CandidateApplyRequest,
    CandidateApplicationResponse,
)

__all__ = [
    "HrRegisterRequest",
    "HrLoginRequest",
    "HrTokenResponse",
    "JobCreateRequest",
    "JobResponse",
    "ApplicationResponse",
    "ApplicationDetailResponse",
    "PaginatedResponse",
    "CandidateApplyRequest",
    "CandidateApplicationResponse",
]
