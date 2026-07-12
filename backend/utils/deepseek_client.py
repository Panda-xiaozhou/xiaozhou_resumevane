"""
DeepSeek API 客户端（增强版）
=============================
使用 OpenAI Python SDK 连接 DeepSeek API（兼容 OpenAI 接口），
提供指数退避重试、Token 用量追踪、成本统计。

使用方式：
    from backend.utils.deepseek_client import get_client, chat_completion, get_usage_stats

    result = await chat_completion(
        messages=[...],
        temperature=0.1,
        max_tokens=2048,
        caller="matcher_node",
    )
    # result 包含 content、usage、cost 字段

配置：
    通过环境变量注入 API Key 和 Base URL，参见 config.py。

重试策略：
    - 对 RateLimitError、APIConnectionError、APITimeoutError、InternalServerError
      进行指数退避重试（2s → 4s → 8s → 16s，最多 3 次）
    - 配置项：LLM_MAX_RETRIES（默认 3）、LLM_TIMEOUT_SECONDS（默认 120）

Token 追踪：
    - 每次调用后自动记录 prompt_tokens、completion_tokens、cost
    - 通过 get_usage_stats() 获取累计用量
    - DeepSeek 定价：chat 输入 ¥1/百万 tokens，输出 ¥2/百万 tokens

维护注意：
  - 更换模型时修改 config.py 中的 DEEPSEEK_MODEL
  - 定价变更时更新 _calculate_cost()
  - 如需切换为其他兼容 OpenAI 接口的模型，仅需改环境变量
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

from openai import OpenAI

from ..config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
)

# ── 重试配置 ──────────────────────────────────────────
LLM_MAX_RETRIES = 3
LLM_TIMEOUT_SECONDS = 120
RETRY_BACKOFF_BASE = 2.0  # 指数底数

# ── 重试判定：哪些异常值得重试 ─────────────────────────
RETRYABLE_EXCEPTIONS = (
    "RateLimitError",
    "APIConnectionError",
    "APITimeoutError",
    "InternalServerError",
    "ServiceUnavailableError",
)


@dataclass
class UsageRecord:
    """单次 LLM 调用的用量记录"""
    caller: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_rmb: float
    duration_ms: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class ChatResult:
    """LLM 调用结果"""
    content: str
    usage: dict
    cost_rmb: float
    duration_ms: float


# ── 全局用量统计 ──────────────────────────────────────
_usage_records: list[UsageRecord] = []

# 延迟初始化——模块导入时不创建客户端，避免因 API Key 占位符导致启动失败
_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    """获取 DeepSeek API 客户端单例（延迟初始化）"""
    global _client
    if _client is None:
        _client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    return _client


def get_model() -> str:
    """获取当前配置的模型名称"""
    return DEEPSEEK_MODEL


def get_usage_stats() -> dict:
    """
    获取累计用量统计。

    返回:
        {
            "total_calls": 总调用次数,
            "total_prompt_tokens": 总输入 token,
            "total_completion_tokens": 总输出 token,
            "total_cost_rmb": 总花费（人民币）,
            "records": 最近 100 条调用记录
        }
    """
    return {
        "total_calls": len(_usage_records),
        "total_prompt_tokens": sum(r.prompt_tokens for r in _usage_records),
        "total_completion_tokens": sum(r.completion_tokens for r in _usage_records),
        "total_cost_rmb": sum(r.cost_rmb for r in _usage_records),
        "records": [
            {
                "caller": r.caller,
                "model": r.model,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "cost_rmb": r.cost_rmb,
                "duration_ms": r.duration_ms,
            }
            for r in _usage_records[-100:]
        ],
    }


def _calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    计算单次调用的成本（人民币）。

    DeepSeek 定价（2025）：
      - deepseek-v4-flash:  输入 ¥0.5/百万 tokens, 输出 ¥2/百万 tokens
      - deepseek-chat:      输入 ¥1/百万 tokens,   输出 ¥2/百万 tokens
      - deepseek-reasoner:  输入 ¥4/百万 tokens,   输出 ¥16/百万 tokens
    """
    if "v4-flash" in model or "v4_flash" in model:
        input_price = 0.5 / 1_000_000
        output_price = 2.0 / 1_000_000
    elif "reasoner" in model:
        input_price = 4.0 / 1_000_000
        output_price = 16.0 / 1_000_000
    else:
        input_price = 1.0 / 1_000_000
        output_price = 2.0 / 1_000_000

    return (prompt_tokens * input_price) + (completion_tokens * output_price)


def _is_retryable(error: Exception) -> bool:
    """判断异常是否值得重试"""
    error_type = type(error).__name__
    if error_type in RETRYABLE_EXCEPTIONS:
        return True
    # 检查状态码（429 / 502 / 503）
    status_code = getattr(error, "status_code", None)
    if status_code and status_code in (429, 502, 503):
        return True
    return False


async def chat_completion(
    messages: list[dict],
    temperature: float = 0.1,
    max_tokens: int = 2048,
    caller: str = "unknown",
    model: Optional[str] = None,
    max_retries: int = LLM_MAX_RETRIES,
    timeout: int = LLM_TIMEOUT_SECONDS,
) -> ChatResult:
    """
    带重试的 LLM 调用封装。

    参数:
        messages: 消息列表
        temperature: 温度参数
        max_tokens: 最大输出 token
        caller: 调用方标识（用于追踪，如 "matcher_node"）
        model: 模型名称，默认使用配置的 DEEPSEEK_MODEL
        max_retries: 最大重试次数
        timeout: 超时时间（秒）

    返回:
        ChatResult，包含 content、usage、cost_rmb、duration_ms

    异常:
        重试耗尽后抛出最后一个异常
    """
    client = get_client()
    model_name = model or DEEPSEEK_MODEL
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            start = time.time()
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: client.chat.completions.create(
                        model=model_name,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                ),
                timeout=timeout,
            )
            duration_ms = (time.time() - start) * 1000

            # 提取用量
            usage = response.usage
            prompt_tokens = usage.prompt_tokens if usage else 0
            completion_tokens = usage.completion_tokens if usage else 0
            cost = _calculate_cost(model_name, prompt_tokens, completion_tokens)
            content = response.choices[0].message.content or ""

            # 记录用量
            _usage_records.append(UsageRecord(
                caller=caller,
                model=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_rmb=cost,
                duration_ms=duration_ms,
            ))

            return ChatResult(
                content=content,
                usage={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
                cost_rmb=cost,
                duration_ms=duration_ms,
            )

        except Exception as e:
            last_error = e
            if attempt < max_retries and _is_retryable(e):
                wait = RETRY_BACKOFF_BASE ** attempt
                await asyncio.sleep(wait)
                continue
            break

    raise last_error  # type: ignore[misc]
