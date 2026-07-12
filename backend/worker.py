"""
ARQ Worker 入口
===============
启动后台任务工作进程，消费 Redis 队列中的筛选任务。

启动方式:
    arq backend.services.task_queue.WorkerSettings --watch backend

Docker 中启动:
    CMD ["arq", "backend.services.task_queue.WorkerSettings", "--watch", "backend"]
"""
# 此文件仅作为 ARQ worker 的入口点
# WorkerSettings 定义在 backend/services/task_queue.py 中
from .services.task_queue import WorkerSettings  # noqa: F401
