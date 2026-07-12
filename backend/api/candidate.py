"""
候选人端 API
============
提供候选人投递简历和查询投递状态的接口。

路由前缀: /api/candidate
认证: 无需登录（公共服务）

接口列表:
  POST /apply          提交投递申请（含简历文件上传）
  GET  /applications   根据邮箱查询投递历史及筛选状态

数据流:
  POST /apply → 保存简历文件 → 获取/创建候选人记录 → 创建投递(pending)
     → 返回 application_id
     （流水线目前需要手动触发或通过后台调用 rescreen）

维护注意：
  - 投递后不自动触发流水线（避免上传大文件时阻塞响应），可通过
    /api/hr/applications/{id}/rescreen 手动触发
  - 未来可接入消息队列（Celery/Redis）实现异步触发
"""
import os
import uuid
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, HTTPException
from sqlalchemy.orm import Session

from ..models.base import get_db
from ..models.application import Application
from ..models.job import Job
from ..models.user import Candidate
from ..services.auth_service import get_or_create_candidate
from ..services.application_service import (
    create_application,
    get_applications_by_candidate,
    schedule_pipeline_background,
)
from ..config import UPLOAD_DIR, MAX_RESUME_SIZE

router = APIRouter(prefix="/api/candidate", tags=["Candidate"])
logger = logging.getLogger(__name__)


@router.post("/apply")
async def candidate_apply(
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    job_id: str = Form(...),
    self_intro: str = Form(""),
    expected_salary: str = Form(""),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    候选人投递简历。

    参数:
        name: 姓名（必填）
        email: 邮箱（必填，用于唯一标识和状态查询）
        phone: 手机号（选填）
        job_id: 投递的岗位 ID
        self_intro: 自我介绍（选填）
        expected_salary: 期望薪资（选填）
        resume: 简历文件（PDF/Word），最大 10MB

    处理流程:
        1. 校验文件格式 → 保存到 UPLOAD_DIR
        2. 查重：如果邮箱已存在候选人记录则复用，否则新建
        3. 创建投递记录（status=pending）
        4. 返回投递确认信息
    """
    # ── 校验 job_id 格式（提前校验，避免存了文件才发现 UUID 无效）──
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(422, f"无效的岗位 ID: {job_id}")

    # ── 校验文件格式 ─────────────────────────────
    ext = os.path.splitext(resume.filename or "resume.pdf")[1].lower()
    if ext not in (".pdf", ".docx", ".doc"):
        raise HTTPException(422, f"不支持的文件格式: {ext}，仅支持 PDF、DOCX、DOC")

    # ── 校验文件大小 ─────────────────────────────
    content = await resume.read()
    if len(content) > MAX_RESUME_SIZE:
        max_mb = MAX_RESUME_SIZE // (1024 * 1024)
        raise HTTPException(413, f"文件大小超过限制（最大 {max_mb}MB）")

    # ── 保存简历文件 ────────────────────────────
    # 文件名用 UUID 避免重名冲突和安全风险
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    try:
        with open(file_path, "wb") as f:
            f.write(content)

        # ── 获取或创建候选人（邮箱去重）───────────────
        candidate = get_or_create_candidate(db, name, email, phone)

        # ── 创建投递记录 ────────────────────────────
        app = create_application(
            db,
            str(candidate.id),
            job_id,
            {
                "self_intro": self_intro,
                "expected_salary": expected_salary,
                "resume_original_name": os.path.basename(resume.filename or ""),
            },
            file_path,
        )
        logger.info(
            "candidate_apply_created application_id=%s candidate_email=%s job_id=%s",
            app.id,
            email,
            job_id,
        )
        schedule_pipeline_background(str(app.id))
        logger.info(
            "candidate_apply_task_scheduled application_id=%s background_task_count=%s",
            app.id,
            len(background_tasks.tasks),
        )

        return {
            "application_id": str(app.id),
            "candidate_name": name,
            "status": app.status,
            "message": "投递成功，简历已进入筛选队列",
        }
    except Exception:
        # 保存或创建投递失败 → 清理已保存的文件
        if os.path.exists(file_path):
            os.remove(file_path)
        raise


@router.get("/applications")
def candidate_applications(email: str, db: Session = Depends(get_db)):
    """
    根据邮箱查询投递历史和筛选状态。

    参数:
        email: 投递时使用的邮箱

    返回:
        该邮箱下所有投递记录列表，含当前状态和匹配分。
        空列表表示未找到记录。
    """
    candidate = db.query(Candidate).filter(Candidate.email == email).first()
    if not candidate:
        return []

    apps = (
        db.query(Application, Job.title)
        .join(Job, Application.job_id == Job.id)
        .filter(Application.candidate_id == candidate.id)
        .order_by(Application.created_at.desc())
        .all()
    )
    return [
        {
            "id": str(app.id),
            "job_id": str(app.job_id),
            "job_title": job_title,
            "status": app.status,
            "match_score": app.match_score,
            "created_at": app.created_at.isoformat(),
        }
        for app, job_title in apps
    ]
