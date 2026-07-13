"""
认证服务
========
提供 HR 用户注册/登录、JWT Token 签发/验证、候选人创建等功能。

安全说明：
  - 密码使用 bcrypt 哈希存储，不可逆
  - JWT Secret 从 JWT_SECRET_KEY 环境变量读取，为空时服务启动失败
  - Token 有效期 24 小时，过期需重新登录

候选人创建策略：
  - 以邮箱为唯一标识去重（get_or_create）
  - 同一邮箱多次投递不会创建重复记录

维护注意：
  - 修改密码哈希方案或 Token 有效期时，需考虑已有用户的影响
  - 生产环境务必使用独立的 JWT_SECRET 环境变量
"""
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import bcrypt
from sqlalchemy.orm import Session

from ..models.user import HrUser, Candidate
from ..models.base import get_db
from ..config import JWT_SECRET_KEY

# ── JWT 配置 ──────────────────────────────────────
SECRET_KEY = JWT_SECRET_KEY
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

# Bearer Token 提取器，用于 FastAPI 依赖注入
_bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """对明文密码做 bcrypt 哈希"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """验证明文密码是否与哈希匹配"""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_token(user_id: str) -> str:
    """
    签发 JWT Token。

    参数:
        user_id: HR 用户的 UUID 字符串
    返回:
        签名的 JWT 字符串，有效期 TOKEN_EXPIRE_HOURS 小时
    """
    expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> str | None:
    """
    验证 JWT Token 并返回用户 ID。

    参数:
        token: Bearer Token 字符串（不含 "Bearer " 前缀）
    返回:
        用户 UUID 字符串，验证失败返回 None
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def create_hr_user(db: Session, username: str, password: str, display_name: str) -> HrUser:
    """创建 HR 用户（注册）"""
    user = HrUser(
        username=username,
        password_hash=hash_password(password),
        display_name=display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_hr_user(db: Session, username: str) -> HrUser | None:
    """根据用户名查找 HR 用户"""
    return db.query(HrUser).filter(HrUser.username == username).first()


def get_or_create_candidate(db: Session, name: str, email: str, phone: str = "") -> Candidate:
    """
    获取或创建候选人（以邮箱去重）。

    如果邮箱已存在，直接返回已有记录（保留首次投递时的信息）；
    如果邮箱不存在，创建新记录。
    """
    candidate = db.query(Candidate).filter(Candidate.email == email).first()
    if candidate:
        return candidate
    candidate = Candidate(name=name, email=email, phone=phone)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> HrUser:
    """
    FastAPI 依赖注入：从 Authorization Bearer header 解析 JWT 并返回当前 HR 用户。

    用法：
        @router.get("/api/hr/jobs")
        def list_jobs(current_user: HrUser = Depends(get_current_user)):
            ...

    异常：
        HTTP 401: Token 缺失、无效或过期
        HTTP 401: 用户不存在（已被删除）
    """
    if not SECRET_KEY:
        raise HTTPException(500, "服务器 JWT_SECRET_KEY 未配置，请联系管理员")

    if credentials is None:
        raise HTTPException(401, "未提供认证凭证，请先登录")

    user_id = verify_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(401, "Token 无效或已过期，请重新登录")

    user = db.query(HrUser).filter(HrUser.id == user_id).first()
    if user is None:
        raise HTTPException(401, "用户不存在")

    return user
