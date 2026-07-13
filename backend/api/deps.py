"""
FastAPI 依赖注入
================
提供认证、分页等通用依赖。
"""
from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..models.base import get_db
from ..services.auth_service import verify_token

# HTTP Bearer Token 认证方案
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> str:
    """
    从请求的 Bearer Token 中提取当前 HR 用户 ID。

    用法：
        @router.get("/api/hr/jobs")
        def list_jobs(
            hr_user_id: str = Depends(get_current_user),
            db: Session = Depends(get_db),
        ):
            ...

    异常：
        HTTPException 401: Token 缺失、无效或过期
    """
    token = credentials.credentials
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Token 无效或已过期，请重新登录")
    return user_id


def get_pagination(
    page: int = Query(default=1, ge=1, description="页码（从 1 开始）"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量（最大 100）"),
) -> dict:
    """
    通用分页参数注入。

    返回 {"skip": int, "limit": int} 可直接用于 SQLAlchemy 查询。
    """
    return {"skip": (page - 1) * page_size, "limit": page_size, "page": page, "page_size": page_size}
