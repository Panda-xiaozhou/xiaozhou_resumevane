"""
ResumeVane — FastAPI 应用入口
=============================
启动方式：
  开发: uvicorn backend.main:app --reload --port 8000
  生产: uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4

访问 API 文档: http://localhost:8000/docs
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import UPLOAD_DIR, DEEPSEEK_API_KEY, JWT_SECRET_KEY
from . import models as _models  # noqa: F401  确保所有模型已注册到 Base.metadata
from .models.base import engine, Base, SessionLocal
from .utils.logging import setup_logging, get_logger

# 导入三个路由模块，各自负责不同端口的 API
from .api.hr import router as hr_router          # HR 后台管理接口
from .api.candidate import router as candidate_router  # 候选人投递接口
from .api.jobs import router as jobs_router      # 岗位公开浏览接口

logger = get_logger(__name__)


def _ensure_pgvector_extension() -> None:
    """在建表前确保 PostgreSQL 已启用 pgvector 扩展。"""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理：
      - 启动时：初始化结构化日志
      - 启动时：校验必需环境变量
      - 启动时：自动创建数据库表
      - 启动时：确保简历上传目录存在
      - 启动时：清理因进程崩溃而卡在 processing 的投递记录
    """
    setup_logging()
    logger.info("app_starting")

    # 校验必需环境变量
    _validate_startup_config()

    # 建表——开发环境用 create_all，生产环境请用 alembic upgrade head
    _ensure_pgvector_extension()
    Base.metadata.create_all(bind=engine)
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # 清理卡住的 processing 记录
    from .services.application_service import reset_stale_processing
    db = SessionLocal()
    try:
        reset_stale_processing(db)
    finally:
        db.close()

    yield
    # 关闭时清理逻辑可在此添加（如关闭连接池等）


app = FastAPI(
    title="ResumeVane",
    description="招聘简历智能筛选多 Agent 系统 —— 基于 LangGraph + DeepSeek 的自动化简历筛选与飞书推送平台",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS 跨域配置 ─────────────────────────────────────
# 开发环境允许所有来源；生产环境应限制为实际前端域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 注册路由 ───────────────────────────────────────────
app.include_router(hr_router)
app.include_router(candidate_router)
app.include_router(jobs_router)


def _validate_startup_config() -> None:
    """启动时校验关键配置是否已设置，缺失则抛出明确错误。"""
    errors = []
    if not DEEPSEEK_API_KEY:
        errors.append("DEEPSEEK_API_KEY 未设置——请在 .env 中配置 DeepSeek API Key")
    if not JWT_SECRET_KEY:
        errors.append(
            "JWT_SECRET_KEY 未设置——请在 .env 中配置 JWT 签名密钥\n"
            "  生成方式: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    if errors:
        raise RuntimeError("启动配置校验失败:\n  " + "\n  ".join(errors))


# ── 健康检查 ───────────────────────────────────────────
@app.get("/api/health")
def health_check():
    """
    K8s / Docker 健康检查端点。

    返回服务运行状态及关键依赖健康信息。
    """
    health = {
        "status": "ok",
        "service": "ResumeVane",
        "version": "0.1.0",
    }
    # 检查数据库连通性
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.commit()
        health["database"] = "ok"
    except Exception as e:
        health["database"] = f"error: {e}"
    return health


# ── 用量统计 ───────────────────────────────────────────
@app.get("/api/usage/stats")
def usage_stats():
    """
    LLM Token 用量统计接口。

    返回累计调用次数、Token 消耗、成本估算。
    """
    from .utils.deepseek_client import get_usage_stats
    return get_usage_stats()
