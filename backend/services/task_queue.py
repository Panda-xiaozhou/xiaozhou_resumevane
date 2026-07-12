"""
后台任务队列（ARQ + Redis）
===========================
使用 ARQ（基于 Redis 的轻量异步任务队列）管理 Agent 筛选流水线。

设计决策：
  选择 ARQ 而非 Celery 的原因：
  1. ARQ 原生支持 async/await（与 FastAPI + LangGraph 一致）
  2. 更轻量——代码量约为 Celery 的 1/3
  3. 与 FastAPI 集成更简单（共享同一事件循环模型）
  4. 适合本项目的中等规模（不需要 Celery 的复杂路由和调度）

使用方式：
  # 启动 Redis（docker-compose up -d redis）
  # 启动 worker
  arq backend.worker.WorkerSettings --watch backend

  # 投递简历后自动入队
  from backend.services.task_queue import enqueue_screening
  job = await enqueue_screening(application_id)

  # 查询任务状态
  from backend.services.task_queue import get_job_result
  result = await get_job_result(job_id)

维护注意：
  - Redis URL 通过 REDIS_URL 环境变量配置
  - Worker 进程需单独启动（见 docker-compose.yml）
  - 函数签名变更时需重启 worker
"""
import asyncio
from typing import Optional

from arq import ArqRedis, create_pool
from arq.jobs import Job, JobStatus

from ..config import AGENT_CONCURRENCY

# Redis 连接配置——默认连接本地 Redis
REDIS_URL = "redis://localhost:6379"

# 全局 Redis 连接池（懒初始化）
_redis_pool: Optional[ArqRedis] = None
_pool_lock = asyncio.Lock()


async def get_redis() -> ArqRedis:
    """获取 Redis 连接池（线程安全、懒初始化）"""
    global _redis_pool
    if _redis_pool is None:
        async with _pool_lock:
            if _redis_pool is None:
                _redis_pool = await create_pool(
                    REDIS_URL,
                    default_queue_name="resumevane:queue",
                )
    return _redis_pool


async def enqueue_screening(application_id: str) -> str:
    """
    将简历筛选任务入队。

    参数:
        application_id: 投递记录 UUID 字符串
    返回:
        任务 ID（JID），可用于查询状态

    投递后自动调用此函数，不需要 HR 手动触发 rescreen。
    任务在 worker 进程中异步执行，不阻塞 HTTP 响应。
    """
    redis = await get_redis()
    job = await redis.enqueue_job(
        "run_pipeline_task",
        application_id,
        _job_id=f"screening:{application_id}",
        _defer_by=0,
    )
    return job.job_id


async def get_job_result(job_id: str) -> Optional[dict]:
    """
    查询异步任务的执行结果。

    参数:
        job_id: 任务 ID
    返回:
        - 任务完成: 返回流水线结果 dict
        - 任务执行中: 返回 {"status": "running"}
        - 任务不存在: 返回 None
    """
    redis = await get_redis()
    job = Job(job_id, redis)

    try:
        status = await job.status()
    except Exception:
        return None

    if status == JobStatus.complete:
        result = await job.result()
        return result if result else {"status": "completed"}
    elif status == JobStatus.not_found:
        return None
    elif status == JobStatus.deferred:
        return {"status": "queued"}
    else:
        return {"status": str(status)}


# ── Worker 任务函数 ──────────────────────────────────
# 这些函数在 ARQ worker 进程中运行
# 函数名对应 enqueue_job 的第一个参数


async def run_pipeline_task(ctx: dict, application_id: str) -> dict:
    """
    Worker 中执行的筛选流水线任务。

    在 worker 进程中创建独立的数据库会话和 Agent 上下文。
    """
    from .application_service import run_pipeline_background

    return await run_pipeline_background(application_id)


# ── Worker 配置类 ────────────────────────────────────
# ARQ 在启动时读取此类的属性以配置 worker


class WorkerSettings:
    """
    ARQ Worker 配置。

    启动命令: arq backend.services.task_queue.WorkerSettings --watch backend
    """
    functions = [run_pipeline_task]
    redis_settings = REDIS_URL
    max_jobs = AGENT_CONCURRENCY  # 并发控制
    job_timeout = 300  # 单个任务超时（秒）= 5 分钟
    keep_result = 3600  # 结果保留时间（秒）= 1 小时
    health_check_interval = 30
