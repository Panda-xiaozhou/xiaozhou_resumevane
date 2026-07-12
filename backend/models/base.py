"""
数据库连接与基础定义
====================
使用 SQLAlchemy 2.0 风格，通过 psycopg2 连接 PostgreSQL。
所有模型继承此 Base，由 main.py 的 lifespan 中自动建表。

维护注意：
  - 生产环境请使用 Alembic 管理数据库迁移（alembic upgrade head）
  - 不要在 create_all 中依赖外键顺序，Alembic 会处理
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from ..config import DATABASE_URL

# 创建数据库引擎
# pool_size: 基础连接数（默认 5 → 10 适应并发 Agent 流水线）
# max_overflow: 峰值时额外连接数（默认 10 → 20）
# pool_pre_ping=True: 取出连接前先 ping 确保有效
# pool_recycle: 连接最大存活时间（秒），防止 PostgreSQL 服务端断开空闲连接后客户端不知
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# 会话工厂——每个请求通过 get_db() 获取独立会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ORM 基类——所有模型文件中的类都继承此 Base
Base = declarative_base()


def get_db():
    """
    FastAPI 依赖注入：为每个请求创建独立的数据库会话，请求结束后自动关闭。
    用法：
        @app.get("/api/xxx")
        def handler(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
