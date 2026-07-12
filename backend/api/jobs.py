"""
岗位公开浏览 API
================
候选人门户使用的公开接口——无需认证即可浏览已发布的岗位。

路由前缀: /api/jobs

接口列表:
  GET /       获取所有已发布岗位列表
  GET /{id}   获取单个岗位详情

注意：仅返回 status="published" 的岗位，草稿和已关闭的岗位不可见。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models.base import get_db
from ..services.job_service import get_published_jobs, get_job

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.get("/")
def list_published_jobs(db: Session = Depends(get_db)):
    """
    获取所有已发布岗位列表。

    返回字段:
        id, title, department, jd_text(截断至前500字符), jd_keywords, created_at
    """
    jobs = get_published_jobs(db)
    return [
        {
            "id": str(j.id),
            "title": j.title,
            "department": j.department,
            # 列表页只显示 JD 前 500 字符，完整内容在详情接口
            "jd_text": j.jd_text[:500],
            "jd_keywords": j.jd_keywords,
            "created_at": j.created_at.isoformat(),
        }
        for j in jobs
    ]


@router.get("/{job_id}")
def get_job_detail(job_id: str, db: Session = Depends(get_db)):
    """
    获取单个岗位的完整详情。

    安全: 仅返回已发布（published）的岗位，试图访问草稿/关闭的岗位返回错误。
    """
    job = get_job(db, job_id)
    if not job or job.status != "published":
        raise HTTPException(404, "岗位不存在或未发布")
    return {
        "id": str(job.id),
        "title": job.title,
        "department": job.department,
        "jd_text": job.jd_text,  # 完整 JD
        "jd_keywords": job.jd_keywords,
        "created_at": job.created_at.isoformat(),
    }
