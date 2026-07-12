"""
结构化日志工具
==============
基于 structlog 提供 JSON 格式的结构化日志输出。

在本地开发时输出可读的控制台格式，在生产环境中输出 JSON 行，
便于 ELK / Loki / Datadog 等日志系统收集。

使用方式：
    from backend.utils.logging import get_logger

    logger = get_logger(__name__)
    logger.info("pipeline_started", application_id="xxx", job_id="yyy")
    logger.error("llm_call_failed", caller="matcher_node", error=str(e))
"""
import logging
import sys

import structlog

from ..config import LOG_LEVEL


def setup_logging() -> None:
    """
    初始化结构化日志配置。

    在应用启动时调用一次（main.py 的 lifespan 中）。
    - 本地开发：彩色控制台输出
    - 生产环境：JSON 行输出到 stdout
    """
    # 判断是否在终端中运行（本地开发 vs 容器/生产）
    is_terminal = sys.stdout.isatty()

    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.set_exc_info,  # type: ignore[attr-defined]
        structlog.processors.format_exc_info,
    ]

    if is_terminal:
        # 开发环境：彩色控制台输出
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # 生产环境：JSON 行输出
        processors = shared_processors + [
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 设置日志级别
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    获取结构化日志记录器。

    参数:
        name: 模块名（通常传 __name__）
    返回:
        structlog BoundLogger 实例
    """
    return structlog.get_logger(name)
