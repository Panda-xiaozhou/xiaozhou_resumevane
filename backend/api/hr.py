"""
HR 后台管理 API
===============
提供 HR 用户的认证、岗位管理、投递管理和筛选操作接口。

路由前缀: /api/hr
认证方式: JWT Bearer Token — 除 /register 和 /login 外，所有端点需在
         Authorization header 中携带 Bearer Token，由 get_current_user 依赖注入校验。

接口列表:
  POST   /register                          HR 注册（公开）
  POST   /login                             HR 登录（公开）
  POST   /jobs                              创建岗位
  GET    /jobs                              获取当前 HR 的岗位列表
  PUT    /jobs/{job_id}/status              更新岗位状态
  GET    /applications                      获取某岗位的投递列表
  GET    /applications/{application_id}     获取投递详情（含 Agent 报告）
  POST   /applications/{application_id}/rescreen  手动触发重新筛选
"""
import mimetypes
import os
import uuid
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Form, UploadFile, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..models.base import SessionLocal, get_db
from ..services.auth_service import create_hr_user, get_hr_user, verify_password, create_token, get_current_user
from ..services.job_service import create_job, get_jobs_by_hr, get_job, update_job_status, update_job, delete_job
from ..services.application_service import (
    delete_applications,
    get_applications_by_job,
    get_application,
    push_selected_applications_to_feishu,
    schedule_pipeline_background,
    run_screening_pipeline,
    update_application_status,
)
from ..models.user import HrUser
from ..config import UPLOAD_DIR
from ..services.embedding_service import (
    delete_job_embeddings,
    embed_job,
    get_job_embedding_detail,
    get_vector_stats,
    list_embedded_jobs,
    list_unembedded_jobs,
    search_similar_jobs,
)

router = APIRouter(prefix="/api/hr", tags=["HR"])

# 岗位状态合法值
VALID_JOB_STATUSES = {"draft", "published", "closed"}

STATUS_LABELS = {
    "pending": "待筛选",
    "processing": "筛选中",
    "passed": "已通过",
    "pending_review": "待复审",
    "screening_failed": "筛选失败",
    "rejected": "未通过",
}


def _get_resume_download_filename(app, candidate_name: str) -> str:
    original_name = os.path.basename((app.form_data or {}).get("resume_original_name", "")).strip()
    if original_name:
        return original_name
    ext = os.path.splitext(app.resume_file or "")[1]
    fallback_name = candidate_name if candidate_name else "candidate"
    return f"{fallback_name}_resume{ext}"


def _get_pipeline_failure_reason(result) -> str:
    if not result:
        return ""
    output_data = result.output_data or {}
    if output_data.get("feishu_push_error"):
        return output_data["feishu_push_error"]
    if result.status == "failed":
        return result.error_message or output_data.get("error", "")
    return result.error_message or ""


async def _embed_job_bg(job_id: str) -> None:
    db = SessionLocal()
    try:
        await embed_job(db, job_id)
    finally:
        db.close()


def build_dashboard_stats(jobs, apps, now: Optional[datetime] = None, trend_days: int = 7) -> dict:
    now = now or datetime.utcnow()
    trend_start = now.date() - timedelta(days=trend_days - 1)

    published_jobs = sum(1 for job in jobs if job.status == "published")
    draft_jobs = sum(1 for job in jobs if job.status == "draft")
    closed_jobs = sum(1 for job in jobs if job.status == "closed")

    window_apps = [app for app in apps if app.created_at.date() >= trend_start]
    status_counter = Counter(app.status for app in window_apps)

    trend_map = {}
    for offset in range(trend_days):
        day = trend_start + timedelta(days=offset)
        trend_map[day] = {
            "date": day.strftime("%m-%d"),
            "applications": 0,
            "passed": 0,
        }

    for app in window_apps:
        app_day = app.created_at.date()
        if app_day in trend_map:
            trend_map[app_day]["applications"] += 1
            if app.status == "passed":
                trend_map[app_day]["passed"] += 1

    job_title_map = {job.id: job.title for job in jobs}
    job_counter = Counter(app.job_id for app in window_apps)
    job_passed_counter = Counter(app.job_id for app in window_apps if app.status == "passed")

    top_jobs = []
    for job_id, application_count in job_counter.most_common(5):
        passed_count = job_passed_counter.get(job_id, 0)
        pass_rate = round((passed_count / application_count) * 100, 1) if application_count else 0.0
        top_jobs.append({
            "job_id": str(job_id),
            "title": job_title_map.get(job_id, "未知岗位"),
            "application_count": application_count,
            "passed_count": passed_count,
            "pass_rate": pass_rate,
        })

    status_distribution = [
        {
            "status": status,
            "label": STATUS_LABELS[status],
            "value": status_counter.get(status, 0),
        }
        for status in ("pending", "processing", "passed", "pending_review", "screening_failed", "rejected")
    ]

    return {
        "total_jobs": len(jobs),
        "published_jobs": published_jobs,
        "draft_jobs": draft_jobs,
        "closed_jobs": closed_jobs,
        "total_applications": len(apps),
        "pending_count": status_counter.get("pending", 0),
        "processing_count": status_counter.get("processing", 0),
        "passed_count": status_counter.get("passed", 0),
        "pending_review_count": status_counter.get("pending_review", 0),
        "screening_failed_count": status_counter.get("screening_failed", 0),
        "rejected_count": status_counter.get("rejected", 0),
        "window_days": trend_days,
        "trend": list(trend_map.values()),
        "status_distribution": status_distribution,
        "top_jobs": top_jobs,
    }


# ═══════════════════════════════════════════════════════
#  认证接口
# ═══════════════════════════════════════════════════════

@router.post("/register")
def register(
    username: str = Form(...),
    password: str = Form(...),
    display_name: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    HR 注册。

    注意：当前没有管理后台的注册审批流程，任何人均可注册。
    生产环境应限制注册（如仅内网可访问、邀请码机制等）。
    """
    existing = get_hr_user(db, username)
    if existing:
        raise HTTPException(400, "用户名已存在")
    user = create_hr_user(db, username, password, display_name)
    return {
        "id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
    }


@router.post("/login")
def login(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    HR 登录——返回 JWT Token。

    返回的 token 应存储在前端 localStorage 中，
    后续需要认证的接口在 Authorization header 中携带。
    """
    user = get_hr_user(db, username)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    token = create_token(str(user.id))
    return {
        "token": token,
        "user_id": str(user.id),
        "display_name": user.display_name,
    }


# ═══════════════════════════════════════════════════════
#  岗位管理接口
# ═══════════════════════════════════════════════════════

@router.post("/jobs")
def hr_create_job(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    department: str = Form(""),
    jd_text: str = Form(...),
    jd_keywords: str = Form(""),
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    """
    创建岗位并自动发布。

    参数:
        title: 岗位名称
        department: 部门（选填）
        jd_text: 岗位描述全文
        jd_keywords: 关键技能词，逗号分隔（如 "Python,FastAPI,React,Docker"）
    """
    # 将逗号分隔的关键词字符串转为列表
    keywords = [k.strip() for k in jd_keywords.split(",") if k.strip()]
    job = create_job(
        db, str(current_user.id),
        {
            "title": title,
            "department": department,
            "jd_text": jd_text,
            "jd_keywords": keywords,
            "status": "published",
        },
    )
    background_tasks.add_task(_embed_job_bg, str(job.id))
    return {
        "id": str(job.id),
        "title": job.title,
        "department": job.department,
        "status": job.status,
        "created_at": job.created_at.isoformat(),
    }


@router.get("/jobs")
def hr_list_jobs(
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    """获取当前 HR 创建的所有岗位"""
    jobs = get_jobs_by_hr(db, str(current_user.id))
    return [
        {
            "id": str(j.id),
            "title": j.title,
            "department": j.department,
            "jd_text": j.jd_text,
            "status": j.status,
            "jd_keywords": j.jd_keywords,
            "created_at": j.created_at.isoformat(),
            "updated_at": j.updated_at.isoformat() if j.updated_at else None,
        }
        for j in jobs
    ]


@router.put("/jobs/{job_id}/status")
def hr_update_job_status(
    job_id: str,
    status: str,
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    """
    更新岗位状态。

    status 可选值:
        published: 发布，候选人可见
        closed: 关闭，候选人不可见
        draft: 草稿（不对外展示）
    """
    if status not in VALID_JOB_STATUSES:
        raise HTTPException(422, f"无效的岗位状态: '{status}'，合法值: {', '.join(sorted(VALID_JOB_STATUSES))}")
    job = update_job_status(db, job_id, status)
    if not job:
        raise HTTPException(404, "岗位不存在")
    return {"id": str(job.id), "status": job.status}


@router.put("/jobs/{job_id}")
def hr_update_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    department: str = Form(""),
    jd_text: str = Form(...),
    jd_keywords: str = Form(""),
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    """
    编辑岗位内容。

    参数与创建岗位相同，传入需要更新的字段值即可。
    """
    keywords = [k.strip() for k in jd_keywords.split(",") if k.strip()]
    job = update_job(db, job_id, {
        "title": title,
        "department": department,
        "jd_text": jd_text,
        "jd_keywords": keywords,
    })
    if not job:
        raise HTTPException(404, "岗位不存在")
    background_tasks.add_task(_embed_job_bg, str(job.id))
    return {
        "id": str(job.id),
        "title": job.title,
        "department": job.department,
        "status": job.status,
        "jd_keywords": job.jd_keywords,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


@router.delete("/jobs/{job_id}")
def hr_delete_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    """
    删除岗位。

    注意：已收到的投递记录不会受影响（级联保留）。
    """
    delete_job_embeddings(db, job_id)
    ok = delete_job(db, job_id)
    if not ok:
        raise HTTPException(404, "岗位不存在")
    return {"detail": "ok"}


@router.get("/dashboard/stats")
def hr_dashboard_stats(
    days: int = Query(7),
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    """
    Dashboard 统计数据。

    返回当前 HR 的岗位总数、投递总数、处理中数量、已通过数量。
    """
    from ..models.application import Application
    from ..models.job import Job as JobModel

    # 当前 HR 的所有岗位 ID
    jobs = get_jobs_by_hr(db, str(current_user.id))
    job_ids = [j.id for j in jobs]

    apps = []

    if job_ids:
        apps = (
            db.query(Application)
            .filter(Application.job_id.in_(job_ids))
            .all()
        )

    trend_days = 30 if days == 30 else 7
    return build_dashboard_stats(jobs, apps, trend_days=trend_days)


@router.post("/jobs/{job_id}/embed")
async def hr_embed_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    result = await embed_job(db, job_id)
    if result.get("error"):
        if result["error"] == "岗位不存在":
            raise HTTPException(404, result["error"])
        raise HTTPException(500, result["error"])
    return result


@router.delete("/jobs/{job_id}/embed")
def hr_delete_job_embedding(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    deleted_count = delete_job_embeddings(db, job_id)
    return {"deleted_count": deleted_count}


@router.post("/jobs/embed-all")
def hr_embed_all_jobs(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    jobs = [job for job in get_jobs_by_hr(db, str(current_user.id)) if job.status == "published"]
    for job in jobs:
        background_tasks.add_task(_embed_job_bg, str(job.id))
    return {"queued_count": len(jobs)}


@router.post("/jobs/reembed-all")
def hr_reembed_all_jobs(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    jobs = [job for job in get_jobs_by_hr(db, str(current_user.id)) if job.status == "published"]
    for job in jobs:
        background_tasks.add_task(_embed_job_bg, str(job.id))
    return {"queued_count": len(jobs)}


@router.get("/vectordb/stats")
def hr_vector_stats(
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    return get_vector_stats(db)


@router.get("/vectordb/jobs")
def hr_vector_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str = Query(""),
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    return list_embedded_jobs(db, page=page, page_size=page_size, search=search)


@router.get("/vectordb/unembedded-jobs")
def hr_vector_unembedded_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str = Query(""),
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    jobs = get_jobs_by_hr(db, str(current_user.id))
    return list_unembedded_jobs(db, jobs, page=page, page_size=page_size, search=search)


@router.get("/jobs/{job_id}/embed")
def hr_job_embedding_detail(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    return get_job_embedding_detail(db, job_id)


@router.get("/jobs/{job_id}/similar-jobs")
async def hr_similar_jobs(
    job_id: str,
    top_k: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    return {"items": await search_similar_jobs(db, job_id, top_k=top_k)}


# ═══════════════════════════════════════════════════════
#  投递管理 & 筛选接口
# ═══════════════════════════════════════════════════════

@router.get("/applications")
def hr_list_applications(
    job_id: str = Query(...),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    """
    获取指定岗位的投递列表，支持状态筛选和候选人搜索。

    查询参数:
        job_id: 岗位 ID（必填）
        status: 状态筛选（pending / processing / passed / pending_review / rejected）
        search: 按候选人姓名或邮箱模糊搜索
    """
    from ..models.agent_result import AgentResult
    from ..models.application import Application
    from ..models.user import Candidate

    query = (
        db.query(Application, Candidate.name, Candidate.email)
        .join(Candidate, Application.candidate_id == Candidate.id)
        .filter(Application.job_id == job_id)
    )

    if status:
        query = query.filter(Application.status == status)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            Candidate.name.ilike(search_filter) | Candidate.email.ilike(search_filter)
        )

    rows = query.order_by(Application.match_score.desc()).all()
    application_ids = [app.id for app, _, _ in rows]

    failure_reason_map = {}
    if application_ids:
        pipeline_results = (
            db.query(AgentResult)
            .filter(AgentResult.application_id.in_(application_ids))
            .filter(AgentResult.agent_name == "pipeline")
            .order_by(AgentResult.created_at.desc())
            .all()
        )
        for pipeline_result in pipeline_results:
            app_id = str(pipeline_result.application_id)
            if app_id in failure_reason_map:
                continue
            failure_reason = _get_pipeline_failure_reason(pipeline_result)
            if failure_reason:
                failure_reason_map[app_id] = failure_reason

    return [
        {
            "id": str(app.id),
            "candidate_id": str(app.candidate_id),
            "candidate_name": name,
            "candidate_email": email,
            "status": app.status,
            "match_score": app.match_score,
            "push_status": app.push_status,
            "failure_reason": failure_reason_map.get(str(app.id), ""),
            "created_at": app.created_at.isoformat(),
        }
        for app, name, email in rows
    ]


@router.get("/applications/{application_id}")
def hr_get_application_detail(
    application_id: str,
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    """
    获取投递详情——含候选人信息、AI 解析结果、筛选报告。
    """
    app = get_application(db, application_id)
    if not app:
        raise HTTPException(404, "投递记录不存在")

    from ..models.agent_result import AgentResult
    from ..models.user import Candidate

    candidate = db.query(Candidate).filter(Candidate.id == app.candidate_id).first()

    # 查询最新的 pipeline 执行结果
    pipeline_result = (
        db.query(AgentResult)
        .filter(AgentResult.application_id == app.id)
        .filter(AgentResult.agent_name == "pipeline")
        .order_by(AgentResult.created_at.desc())
        .first()
    )

    # 查询 parser 节点的解析结果（AI 提取的结构化简历）
    parser_result = (
        db.query(AgentResult)
        .filter(AgentResult.application_id == app.id)
        .filter(AgentResult.agent_name == "parser")
        .order_by(AgentResult.created_at.desc())
        .first()
    )

    agent_data = pipeline_result.output_data if pipeline_result else {}

    parsed_resume = {}
    if parser_result:
        parsed_resume = parser_result.output_data.get("parsed_resume", {})
    elif pipeline_result:
        parsed_resume = pipeline_result.output_data.get("parsed_resume", {})

    return {
        "id": str(app.id),
        "status": app.status,
        "match_score": app.match_score,
        "push_status": app.push_status,
        "failure_reason": _get_pipeline_failure_reason(pipeline_result),
        "form_data": app.form_data,
        "resume_file": app.resume_file,
        "resume_download_url": f"/api/hr/applications/{application_id}/resume",
        "created_at": app.created_at.isoformat(),
        "candidate": {
            "name": candidate.name if candidate else "",
            "email": candidate.email if candidate else "",
            "phone": candidate.phone if candidate else "",
        },
        "parsed_resume": parsed_resume,
        "agent_result": agent_data,
    }


@router.put("/applications/{application_id}/status")
def hr_override_application_status(
    application_id: str,
    status: str = Query(...),
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    """
    手动覆盖 AI 筛选决策。

    status 可选: passed / pending_review / rejected
    仅当投递状态为 passed/pending_review/rejected 时可覆盖。
    """
    if status not in ("passed", "pending_review", "rejected"):
        raise HTTPException(422, "无效状态，合法值: passed, pending_review, rejected")

    app = get_application(db, application_id)
    if not app:
        raise HTTPException(404, "投递记录不存在")

    allowed = {"passed", "pending_review", "rejected"}
    if app.status not in allowed:
        raise HTTPException(400, f"当前状态 '{app.status}' 不允许手动覆盖，请等待筛选完成")

    app = update_application_status(db, application_id, status)
    return {"detail": "ok", "status": app.status}


@router.get("/applications/{application_id}/resume")
def hr_download_resume(
    application_id: str,
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    """
    下载候选人原始简历文件。
    """
    app = get_application(db, application_id)
    if not app:
        raise HTTPException(404, "投递记录不存在")

    if not app.resume_file or not os.path.isfile(app.resume_file):
        raise HTTPException(404, "简历文件不存在或已删除")

    from ..models.user import Candidate
    candidate = db.query(Candidate).filter(Candidate.id == app.candidate_id).first()
    filename = _get_resume_download_filename(app, candidate.name if candidate else "candidate")
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    return FileResponse(app.resume_file, filename=filename, media_type=media_type)


@router.post("/applications/{application_id}/rescreen")
async def hr_rescreen_application(
    application_id: str,
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    """手动触发重新筛选。"""
    result = await run_screening_pipeline(db, application_id)
    if result.get("error"):
        raise HTTPException(500, result["error"])
    return result


@router.post("/jobs/{job_id}/rescreen-all")
async def hr_batch_rescreen(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    """
    批量触发筛选——将该岗位下当前全部投递逐个送入流水线。
    """
    from ..models.application import Application

    apps = (
        db.query(Application)
        .filter(Application.job_id == job_id)
        .all()
    )

    for app in apps:
        schedule_pipeline_background(str(app.id))

    return {"queued_count": len(apps)}


@router.post("/applications/rescreen-selected")
async def hr_rescreen_selected_applications(
    application_ids: list[str] = Body(...),
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    """按当前勾选项批量触发重筛。"""
    if not application_ids:
        raise HTTPException(400, "请先选择投递记录")

    from ..models.application import Application

    jobs = get_jobs_by_hr(db, str(current_user.id))
    allowed_job_ids = {job.id for job in jobs}

    rows = (
        db.query(Application)
        .filter(Application.id.in_(application_ids))
        .filter(Application.job_id.in_(allowed_job_ids))
        .all()
    )

    found_ids = {str(app.id) for app in rows}
    missing_ids = [app_id for app_id in application_ids if app_id not in found_ids]

    for app in rows:
        schedule_pipeline_background(str(app.id))

    return {
        "queued_count": len(rows),
        "requested_count": len(application_ids),
        "missing_ids": missing_ids,
    }


@router.post("/applications/actions/delete-selected")
def hr_delete_selected_applications(
    application_ids: list[str] = Body(...),
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    """按当前勾选项批量删除投递。"""
    if not application_ids:
        raise HTTPException(400, "请先选择投递记录")

    from ..models.application import Application

    jobs = get_jobs_by_hr(db, str(current_user.id))
    allowed_job_ids = {job.id for job in jobs}
    rows = (
        db.query(Application)
        .filter(Application.id.in_(application_ids))
        .filter(Application.job_id.in_(allowed_job_ids))
        .all()
    )

    found_ids = [str(app.id) for app in rows]
    missing_ids = [application_id for application_id in application_ids if application_id not in found_ids]
    deleted_count = delete_applications(db, found_ids)

    return {
        "deleted_count": deleted_count,
        "requested_count": len(application_ids),
        "missing_ids": missing_ids,
    }


@router.post("/applications/actions/push-selected")
async def hr_push_selected_applications(
    application_ids: list[str] = Body(...),
    db: Session = Depends(get_db),
    current_user: HrUser = Depends(get_current_user),
):
    """按当前勾选项批量推送飞书卡片和 PDF 简历。"""
    if not application_ids:
        raise HTTPException(400, "请先选择投递记录")

    jobs = get_jobs_by_hr(db, str(current_user.id))
    allowed_job_ids = {job.id for job in jobs}
    return await push_selected_applications_to_feishu(db, application_ids, allowed_job_ids)
