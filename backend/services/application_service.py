"""
投递管理服务
============
核心业务服务，负责：
  1. 投递记录的创建和管理
  2. Agent 筛选流水线的触发和状态管理
  3. 筛选结果的持久化和状态回写

流水线触发流程：
  候选人投递 → create_application("pending")
       → run_screening_pipeline() → status = "processing"
           → Agent 流水线执行 → 结果落库
               → 推荐: status = "passed", push_status = "pushing"
               → 待定: status = "pending_review"
               → 不推荐: status = "rejected"

维护注意：
  - run_screening_pipeline 是 CPU/IO 密集型操作，生产环境应改为
    Celery/Redis 后台任务队列，避免阻塞 FastAPI 事件循环
  - Agent 流水线超时时间目前依赖 LangGraph 内部超时，建议加外层超时控制
"""
import asyncio
import uuid
import os
import logging

from sqlalchemy.orm import Session

from ..models.application import Application
from ..models.agent_result import AgentResult
from ..models.base import SessionLocal
from ..models.job import Job
from ..agents.graph import resume_screening_graph
from ..agents.state import AgentState
from ..config import PASS_THRESHOLD, REVIEW_THRESHOLD

logger = logging.getLogger(__name__)
_scheduled_pipeline_tasks: set[asyncio.Task] = set()


def schedule_pipeline_background(application_id: str) -> None:
    """显式调度后台筛选任务，避免依赖响应结束后的 BackgroundTasks 执行时机。"""
    task = asyncio.create_task(run_pipeline_background(application_id))
    _scheduled_pipeline_tasks.add(task)
    task.add_done_callback(_scheduled_pipeline_tasks.discard)
    logger.info("schedule_pipeline_background application_id=%s", application_id)


def create_application(
    db: Session, candidate_id: str, job_id: str, form_data: dict, resume_file: str
) -> Application:
    """
    创建投递记录。

    参数:
        db: 数据库会话
        candidate_id: 候选人 UUID 字符串
        job_id: 岗位 UUID 字符串
        form_data: 候选人填写的表单数据（自我介绍、期望薪资等）
        resume_file: 简历文件在服务器上的绝对路径
    返回:
        新创建的 Application 对象
    """
    app = Application(
        candidate_id=uuid.UUID(candidate_id),
        job_id=uuid.UUID(job_id),
        form_data=form_data,
        resume_file=resume_file,
        status="pending",
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


def get_applications_by_job(db: Session, job_id: str) -> list[Application]:
    """获取某个岗位的所有投递记录，按匹配分降序排列"""
    return (
        db.query(Application)
        .filter(Application.job_id == uuid.UUID(job_id))
        .order_by(Application.match_score.desc())
        .all()
    )


def get_applications_by_candidate(db: Session, candidate_id: str) -> list[Application]:
    """获取某个候选人的所有投递记录，按时间降序"""
    return (
        db.query(Application)
        .filter(Application.candidate_id == uuid.UUID(candidate_id))
        .order_by(Application.created_at.desc())
        .all()
    )


def get_application(db: Session, application_id: str) -> Application | None:
    """根据 ID 查询单条投递记录"""
    return db.query(Application).filter(Application.id == uuid.UUID(application_id)).first()


def update_application_status(db: Session, application_id: str, status: str) -> Application | None:
    """更新投递记录的状态"""
    app = get_application(db, application_id)
    if app:
        app.status = status
        db.commit()
        db.refresh(app)
    return app


async def run_pipeline_background(application_id: str) -> dict:
    """涓虹粓绔姹傚悗鐨勫悗鍙颁换鍔″垱寤虹嫭绔?DB 浼氳瘽銆?"""
    logger.info("run_pipeline_background_started application_id=%s", application_id)
    db = SessionLocal()
    try:
        result = await run_screening_pipeline(db, application_id)
        logger.info(
            "run_pipeline_background_finished application_id=%s result=%s",
            application_id,
            result,
        )
        return result
    except Exception:
        logger.exception("run_pipeline_background_failed application_id=%s", application_id)
        raise
    finally:
        db.close()


async def run_screening_pipeline(db: Session, application_id: str) -> dict:
    """
    运行 Agent 筛选流水线——核心方法。

    执行步骤：
      1. 查询投递记录和关联的岗位信息
      2. 构建 AgentState 初始状态
      3. 调用 LangGraph 编译后的 Graph 执行流水线
      4. 将最终结果写入 agent_results 表
      5. 根据 decision 更新 application 的 status 和 match_score
      6. 返回结果摘要供 API 响应

    异常处理：
      流水线异常时回滚 status 到 "pending"，返回错误信息。
      不会抛出异常——所有错误通过返回 dict 中的 "error" 字段传递。

    性能注意：
      这是一个 async 方法但内部有大量同步 DB 操作。
      生产环境中建议：
        a) 使用 run_in_executor 将同步 DB 操作放到线程池
        b) 或使用 asyncpg + SQLAlchemy async 模式
    """
    app = get_application(db, application_id)
    if not app:
        return {"error": "投递记录不存在"}

    job = db.query(Job).filter(Job.id == app.job_id).first()
    if not job:
        return {"error": "岗位不存在"}

    # ── 标记处理中 ────────────────────────────────────
    app.status = "processing"
    db.commit()

    # ── 构建初始状态 —— 每个字段定义见 agents/state.py ──
    initial_state: AgentState = {
        "application_id": str(app.id),
        "job_id": str(job.id),
        "jd_text": job.jd_text,
        "jd_keywords": job.jd_keywords or [],
        "match_config": job.match_config or {
            "hard_skill": 0.4,
            "education": 0.2,
            "experience": 0.25,
            "project": 0.15,
        },
        "resume_file_path": app.resume_file,
        "parsed_resume": {},
        "match_score": 0.0,
        "dimension_scores": {},
        "matched_keywords": [],
        "missing_keywords": [],
        "highlights": [],
        "risks": [],
        "overall_flag": "yellow",
        "report_markdown": "",
        "recommend": "待定",
        "decision_reason": "",
        "messages": [],
        "step": "start",
        "error": "",
    }

    # ── 执行 LangGraph 流水线 ─────────────────────────
    try:
        # ainvoke 是 LangGraph 的异步调用入口
        final_state = await resume_screening_graph.ainvoke(initial_state)

        # ── 检查流水线是否在 Agent 层报错 ──────────────
        pipeline_error = final_state.get("error", "")
        if pipeline_error:
            # Agent 节点报错 —— 保存失败结果，回滚状态
            agent_result = AgentResult(
                application_id=app.id,
                agent_name="pipeline",
                status="failed",
                output_data={
                    "error": pipeline_error,
                    "step": final_state.get("step", "unknown"),
                    "match_score": final_state.get("match_score", 0),
                },
                error_message=pipeline_error,
            )
            db.add(agent_result)
            app.status = "pending"
            db.commit()
            return {"error": f"流水线执行失败: {pipeline_error}"}

        # ── 保存 Agent 结果 ────────────────────────────
        agent_result = AgentResult(
            application_id=app.id,
            agent_name="pipeline",
            status="completed",
            output_data={
                "match_score": final_state.get("match_score", 0),
                "dimension_scores": final_state.get("dimension_scores", {}),
                "matched_keywords": final_state.get("matched_keywords", []),
                "missing_keywords": final_state.get("missing_keywords", []),
                "highlights": final_state.get("highlights", []),
                "risks": final_state.get("risks", []),
                "overall_flag": final_state.get("overall_flag", "yellow"),
                "recommend": final_state.get("recommend", "待定"),
                "decision_reason": final_state.get("decision_reason", ""),
                "report_markdown": final_state.get("report_markdown", ""),
            },
        )
        db.add(agent_result)

        # ── 状态回写 —— 见 Application 状态机注释 ──────
        recommend = final_state.get("recommend", "待定")
        if recommend == "推荐":
            app.status = "passed"
            # 触发飞书推送
            await _try_push_to_feishu(app, final_state)
        elif recommend == "待定":
            app.status = "pending_review"
        else:
            app.status = "rejected"

        app.match_score = final_state.get("match_score", 0)
        db.commit()

        return {
            "application_id": str(app.id),
            "status": app.status,
            "match_score": app.match_score,
            "recommend": recommend,
            "decision_reason": final_state.get("decision_reason", ""),
            "report_markdown": final_state.get("report_markdown", ""),
        }

    except Exception as e:
        # ── 异常恢复 —— 回滚状态避免数据不一致 ─────────
        app.status = "pending"
        db.commit()
        logger.exception("流水线执行异常: %s", e)
        return {"error": f"流水线执行失败: {str(e)}"}


async def _try_push_to_feishu(app: Application, final_state: dict) -> None:
    """
    尝试推送到飞书群聊——成功更新 push_status 为 pushed，失败降级为 failed。
    推送失败不阻塞流水线。
    """
    try:
        from ..services.feishu_service import get_feishu_client, build_candidate_card

        client = get_feishu_client()
        card = build_candidate_card(
            name=final_state.get("parsed_resume", {}).get("name", "未知"),
            match_score=final_state.get("match_score", 0),
            matched_skills=final_state.get("matched_keywords", []),
            highlights=final_state.get("highlights", []),
            report_md=final_state.get("report_markdown", ""),
        )
        success = await client.send_card(card)
        app.push_status = "pushed" if success else "failed"
        if not success:
            logger.warning("飞书推送失败: application_id=%s", app.id)
    except Exception:
        app.push_status = "failed"
        logger.exception("飞书推送异常: application_id=%s", app.id)


def reset_stale_processing(db: Session, stale_minutes: int = 30) -> int:
    """
    清理长时间卡在 'processing' 状态的投递记录。
    在应用启动时调用，恢复因进程崩溃而卡住的记录。

    返回:
        被重置的记录数
    """
    from datetime import datetime, timedelta

    cutoff = datetime.utcnow() - timedelta(minutes=stale_minutes)
    count = (
        db.query(Application)
        .filter(
            Application.status == "processing",
            Application.updated_at < cutoff,
        )
        .update({"status": "pending"})
    )
    db.commit()
    if count:
        logger.info("重置了 %d 条卡在 processing 超过 %d 分钟的投递记录", count, stale_minutes)
    return count
