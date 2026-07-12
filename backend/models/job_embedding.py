"""
岗位向量存储模型
================
使用 pgvector 扩展存储岗位 JD 的 BGE-M3 向量。
当前按岗位存储两类向量：JD 全文、关键词拼接；标题向量字段预留。
"""
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class JobEmbedding(Base):
    __tablename__ = "job_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    embedding_type = Column(String(32), nullable=False, default="jd_full")
    content_text = Column(Text, nullable=False)
    embedding = Column(Vector(1024), nullable=False)
    model_name = Column(String(64), nullable=False, default="BAAI/bge-m3")
    dim = Column(Integer, nullable=False, default=1024)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
