"""
岗位管理服务
============
提供岗位的 CRUD 操作，供 API 路由层调用。

状态流转：
  draft → published（发布，候选人可见）
  published → closed（关闭，候选人不可见但已有投递保留）
"""
import uuid
from sqlalchemy.orm import Session
from ..models.job import Job


def create_job(db: Session, hr_user_id: str, data: dict) -> Job:
    """
    创建岗位。

    参数:
        db: 数据库会话
        hr_user_id: HR 用户 UUID 字符串
        data: 岗位信息，包含 title, department, jd_text, jd_keywords, match_config, status
    返回:
        新创建的 Job 对象
    """
    job = Job(
        hr_user_id=uuid.UUID(hr_user_id),
        title=data["title"],
        department=data.get("department", ""),
        jd_text=data["jd_text"],
        jd_keywords=data.get("jd_keywords", []),
        match_config=data.get("match_config", {}),
        status=data.get("status", "draft"),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_jobs_by_hr(db: Session, hr_user_id: str) -> list[Job]:
    """获取某个 HR 创建的所有岗位，按创建时间倒序"""
    return (
        db.query(Job)
        .filter(Job.hr_user_id == uuid.UUID(hr_user_id))
        .order_by(Job.created_at.desc())
        .all()
    )


def get_published_jobs(db: Session) -> list[Job]:
    """获取所有已发布且未关闭的岗位（候选人门户展示用）"""
    return (
        db.query(Job)
        .filter(Job.status == "published")
        .order_by(Job.created_at.desc())
        .all()
    )


def get_job(db: Session, job_id: str) -> Job | None:
    """根据 ID 查询单个岗位"""
    return db.query(Job).filter(Job.id == uuid.UUID(job_id)).first()


def update_job_status(db: Session, job_id: str, status: str) -> Job | None:
    """更新岗位状态（发布/关闭）"""
    job = get_job(db, job_id)
    if job:
        job.status = status
        db.commit()
        db.refresh(job)
    return job


def update_job(db: Session, job_id: str, data: dict) -> Job | None:
    """
    更新岗位内容。

    参数:
        db: 数据库会话
        job_id: 岗位 UUID
        data: 需要更新的字段，可选 title, department, jd_text, jd_keywords
    返回:
        更新后的 Job 对象，不存在返回 None
    """
    job = get_job(db, job_id)
    if not job:
        return None
    if "title" in data:
        job.title = data["title"]
    if "department" in data:
        job.department = data["department"]
    if "jd_text" in data:
        job.jd_text = data["jd_text"]
    if "jd_keywords" in data:
        job.jd_keywords = data["jd_keywords"]
    db.commit()
    db.refresh(job)
    return job


def delete_job(db: Session, job_id: str) -> bool:
    """
    删除岗位。

    返回:
        True 表示删除成功，False 表示岗位不存在
    """
    job = get_job(db, job_id)
    if not job:
        return False
    db.delete(job)
    db.commit()
    return True
