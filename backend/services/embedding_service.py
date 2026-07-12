"""
向量嵌入管理服务
================
负责岗位 JD 向量的生成、删除、统计和列表查询。
"""
import uuid
from collections import Counter
from datetime import datetime

from sqlalchemy.orm import Session

from ..config import EMBEDDING_DIM, EMBEDDING_MODEL
from ..models.job import Job
from ..models.job_embedding import JobEmbedding
from ..utils.embedding import cosine_similarity, embed_texts


EMBEDDING_TYPES = ("jd_full", "jd_keywords", "jd_title")


def build_job_embedding_texts(job: Job) -> list[tuple[str, str]]:
    texts_to_embed: list[tuple[str, str]] = []
    jd_text = (job.jd_text or "").strip()
    if jd_text:
        texts_to_embed.append(("jd_full", jd_text[:4000]))

    keywords = [keyword.strip() for keyword in (job.jd_keywords or []) if keyword.strip()]
    if keywords:
        texts_to_embed.append(("jd_keywords", "、".join(keywords)))

    title = (job.title or "").strip()
    if title:
        texts_to_embed.append(("jd_title", title))

    return texts_to_embed


async def embed_job(db: Session, job_id: str) -> dict:
    job = db.query(Job).filter(Job.id == uuid.UUID(job_id)).first()
    if not job:
        return {"error": "岗位不存在"}

    texts_to_embed = build_job_embedding_texts(job)
    if not texts_to_embed:
        return {"error": "岗位缺少可向量化文本"}

    try:
        vectors = await embed_texts([item[1] for item in texts_to_embed])
    except Exception as exc:
        return {"error": f"embedding 生成失败: {exc}"}

    delete_job_embeddings(db, job_id, commit=False)

    result = {embedding_type: False for embedding_type in EMBEDDING_TYPES}
    for (embedding_type, content_text), vector in zip(texts_to_embed, vectors):
        db.add(
            JobEmbedding(
                job_id=job.id,
                embedding_type=embedding_type,
                content_text=content_text,
                embedding=vector,
                model_name=EMBEDDING_MODEL,
                dim=EMBEDDING_DIM,
            )
        )
        result[embedding_type] = True

    db.commit()
    return result


def delete_job_embeddings(db: Session, job_id: str, commit: bool = True) -> int:
    deleted_count = (
        db.query(JobEmbedding)
        .filter(JobEmbedding.job_id == uuid.UUID(job_id))
        .delete()
    )
    if commit:
        db.commit()
    return deleted_count


def get_job_embeddings(db: Session, job_id: str) -> list[JobEmbedding]:
    return (
        db.query(JobEmbedding)
        .filter(JobEmbedding.job_id == uuid.UUID(job_id))
        .order_by(JobEmbedding.embedding_type.asc())
        .all()
    )


def get_vector_stats(db: Session) -> dict:
    embeddings = db.query(JobEmbedding).all()
    counter = Counter(embedding.embedding_type for embedding in embeddings)
    latest = max((embedding.updated_at for embedding in embeddings), default=None)
    embedded_jobs = {str(embedding.job_id) for embedding in embeddings}

    return {
        "total_vectors": len(embeddings),
        "embedded_jobs": len(embedded_jobs),
        "by_type": {embedding_type: counter.get(embedding_type, 0) for embedding_type in EMBEDDING_TYPES},
        "model_name": EMBEDDING_MODEL,
        "dimension": EMBEDDING_DIM,
        "latest_update": latest.isoformat() if latest else None,
    }


def build_unembedded_jobs(jobs, embedded_job_ids: set[str], page: int, page_size: int, search: str = "") -> dict:
    search_text = search.strip().lower()
    items = []

    for job in jobs:
        job_id = str(job.id)
        if job_id in embedded_job_ids:
            continue
        if search_text and search_text not in (job.title or "").lower():
            continue
        items.append(
            {
                "job_id": job_id,
                "title": job.title,
                "status": job.status,
                "created_at": job.created_at.isoformat() if getattr(job, "created_at", None) else None,
            }
        )

    start = (page - 1) * page_size
    end = start + page_size
    return {
        "total": len(items),
        "page": page,
        "page_size": page_size,
        "items": items[start:end],
    }


def list_embedded_jobs(db: Session, page: int, page_size: int, search: str = "") -> dict:
    rows = (
        db.query(JobEmbedding, Job)
        .join(Job, JobEmbedding.job_id == Job.id)
        .order_by(JobEmbedding.updated_at.desc())
        .all()
    )

    grouped: dict[str, dict] = {}
    search_text = search.strip().lower()

    for embedding, job in rows:
        job_key = str(job.id)
        if search_text and search_text not in (job.title or "").lower():
            continue
        item = grouped.setdefault(
            job_key,
            {
                "job_id": job_key,
                "title": job.title,
                "status": job.status,
                "has_jd_full": False,
                "has_jd_keywords": False,
                "has_jd_title": False,
                "updated_at": embedding.updated_at.isoformat() if embedding.updated_at else None,
            },
        )
        item[f"has_{embedding.embedding_type}"] = True
        if embedding.updated_at and (
            not item["updated_at"] or embedding.updated_at.isoformat() > item["updated_at"]
        ):
            item["updated_at"] = embedding.updated_at.isoformat()

    items = sorted(grouped.values(), key=lambda item: item["updated_at"] or "", reverse=True)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "total": len(items),
        "page": page,
        "page_size": page_size,
        "items": items[start:end],
    }


def list_unembedded_jobs(db: Session, jobs, page: int, page_size: int, search: str = "") -> dict:
    embedded_job_ids = {str(row.job_id) for row in db.query(JobEmbedding.job_id).distinct().all()}
    return build_unembedded_jobs(jobs, embedded_job_ids, page=page, page_size=page_size, search=search)


def get_job_embedding_detail(db: Session, job_id: str) -> dict:
    embeddings = get_job_embeddings(db, job_id)
    items = [
        {
            "embedding_type": embedding.embedding_type,
            "content_text": embedding.content_text,
            "model_name": embedding.model_name,
            "dim": embedding.dim,
            "updated_at": embedding.updated_at.isoformat() if embedding.updated_at else None,
        }
        for embedding in embeddings
    ]
    return {
        "job_id": job_id,
        "items": items,
    }


async def search_similar_jobs(db: Session, job_id: str, top_k: int = 5) -> list[dict]:
    target = (
        db.query(JobEmbedding)
        .filter(
            JobEmbedding.job_id == uuid.UUID(job_id),
            JobEmbedding.embedding_type == "jd_full",
        )
        .first()
    )
    if not target:
        return []

    candidates = (
        db.query(JobEmbedding, Job)
        .join(Job, JobEmbedding.job_id == Job.id)
        .filter(
            JobEmbedding.job_id != uuid.UUID(job_id),
            JobEmbedding.embedding_type == "jd_full",
        )
        .all()
    )

    similar_jobs = []
    for embedding, job in candidates:
        similarity = round(cosine_similarity(target.embedding, embedding.embedding), 4)
        similar_jobs.append(
            {
                "job_id": str(job.id),
                "job_title": job.title,
                "similarity": similarity,
            }
        )

    similar_jobs.sort(key=lambda item: item["similarity"], reverse=True)
    return similar_jobs[:top_k]
