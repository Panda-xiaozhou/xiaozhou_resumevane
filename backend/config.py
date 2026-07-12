"""
ResumeVane 全局配置文件
=======================
所有环境相关配置统一从此文件读取，通过环境变量注入。
本地开发时，复制 .env.example 为 .env 并填入真实值。
生产部署时，通过 Docker Compose environment 或 K8s ConfigMap 注入。

维护注意：
  - 禁止对内部配置使用 || 或其他方式兜底默认值（遵守 CLAUDE.md 规范）
  - 仅对外部不可信输入做防御处理
  - 新增配置项时同步更新 .env.example
"""
import os

from dotenv import load_dotenv

# 加载 .env 文件（本地开发用；生产环境通过容器注入，文件不存在时静默跳过）
load_dotenv()


def _int_env(key: str, default: int) -> int:
    """安全地将环境变量解析为 int，非数字值时给出明确错误后退出。"""
    raw = os.getenv(key, str(default))
    try:
        return int(raw)
    except ValueError:
        raise ValueError(
            f"环境变量 {key} 的值 '{raw}' 不是有效的整数，请检查 .env 配置"
        )


# ── 数据库 ──────────────────────────────────────────────
# PostgreSQL 连接串格式: postgresql://用户:密码@主机:端口/数据库名
# 本地开发连 Docker 起的 pgvector 容器；生产替换为云数据库地址
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/resumevane")

# ── DeepSeek LLM ────────────────────────────────────────
# 必填：在 https://platform.deepseek.com 注册获取 API Key
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
# API 基础地址（一般无需改动，除非使用代理或私有化部署）
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
# 模型名称：deepseek-v4-flash（快思考）或 deepseek-chat（通用）
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

# ── BGE Embedding（向量化，第三方 API）──────────────────
# BGE（BAAI General Embedding）是智源开源的中文语义向量模型，
# 通过第三方 API（如硅基流动 SiliconFlow）以 OpenAI 兼容接口调用
# 推荐模型: BAAI/bge-m3（多语言，1024 维，支持中英文混合检索）
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
# BGE-M3 向量维度 = 1024
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

# ── JWT 认证 ────────────────────────────────────────────
# 生产环境务必设置！用于签发和验证 HR 登录 Token（HS256）
# 生成方式: python -c "import secrets; print(secrets.token_urlsafe(32))"
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")

# ── 飞书开放平台 ────────────────────────────────────────
# 需要在飞书开放平台创建自建应用，获取以下凭证
# 飞书应用 App ID（以 cli_ 开头）
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
# 飞书应用 App Secret
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
# 推送目标：飞书群聊 chat_id（以 oc_ 开头），不填则不推送
FEISHU_CHAT_ID = os.getenv("FEISHU_CHAT_ID", "")
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")

# ── 文件存储 ─────────────────────────────────────────────
# 候选人上传的简历存放目录，需确保进程有读写权限
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
# 简历文件最大体积（字节），默认 10MB
MAX_RESUME_SIZE = _int_env("MAX_RESUME_SIZE", 10 * 1024 * 1024)

# ── Agent 运行参数 ──────────────────────────────────────
# Agent ReAct 循环最大轮次，防止无限循环消耗 Token
AGENT_MAX_ITERATIONS = _int_env("AGENT_MAX_ITERATIONS", 5)
# 批量简历并行处理的最大并发数，受 DeepSeek API 并发限制约束
AGENT_CONCURRENCY = _int_env("AGENT_CONCURRENCY", 3)
# LLM API 调用超时（秒）
LLM_TIMEOUT_SECONDS = _int_env("LLM_TIMEOUT_SECONDS", 120)
# LLM 调用失败最大重试次数（指数退避：2s → 4s → 8s → 16s）
LLM_MAX_RETRIES = _int_env("LLM_MAX_RETRIES", 3)

# ── 日志 ──────────────────────────────────────────────
# 日志级别: DEBUG | INFO | WARNING | ERROR
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ── 审批决策阈值 ────────────────────────────────────────
# 匹配度 ≥ 此值 且 综合评级 green → 自动推荐（推送到飞书）
PASS_THRESHOLD = _int_env("PASS_THRESHOLD", 75)
# 匹配度 ≥ 此值 且 综合评级非 red → 待定（进入 HR 人工复审队列）
# 低于此值 → 不推荐（静默归档）
REVIEW_THRESHOLD = _int_env("REVIEW_THRESHOLD", 60)
SEMANTIC_MATCH_THRESHOLD = float(os.getenv("SEMANTIC_MATCH_THRESHOLD", "0.7"))
