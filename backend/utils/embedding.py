"""
向量 Embedding 服务（BGE 模型 + 第三方 API）
============================================
使用 BGE-M3（BAAI General Embedding，智源开源）通过第三方 API
生成文本向量，供 Agent 匹配节点做语义相似度检索。

API 提供商（OpenAI 兼容接口）：
  默认: 硅基流动 SiliconFlow（https://api.siliconflow.cn/v1）
  模型: BAAI/bge-m3（多语言，1024 维）

也可切换到其他支持 BGE 的第三方 API（如阿里云百炼、智谱等），
只需修改 EMBEDDING_BASE_URL 和 EMBEDDING_MODEL 环境变量。

使用方式：
    from backend.utils.embedding import embed_texts, cosine_similarity

    embeddings = await embed_texts(["Python", "FastAPI", "Docker"])
    sim = cosine_similarity(embeddings[0], embeddings[1])

维护注意：
  - BGE-M3 向量维度 = 1024
  - 向量已 L2 归一化，余弦相似度即点积
  - 批量请求建议单次不超过 100 条文本
"""
import math
from typing import Optional

from openai import OpenAI

from ..config import (
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_MODEL,
    EMBEDDING_DIM,
    SEMANTIC_MATCH_THRESHOLD,
)


# 延迟初始化——模块导入时不创建客户端，避免因 API Key 占位符导致启动失败
_embedding_client: Optional[OpenAI] = None


def _get_embedding_client() -> OpenAI:
    """获取 Embedding API 客户端单例（延迟初始化）"""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = OpenAI(
            api_key=EMBEDDING_API_KEY,
            base_url=EMBEDDING_BASE_URL,
        )
    return _embedding_client


def get_embedding_dim() -> int:
    """获取当前 embedding 模型的向量维度"""
    return EMBEDDING_DIM


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    使用 BGE 模型将文本列表转换为向量。

    参数:
        texts: 待向量化的文本列表
    返回:
        向量列表，每个向量维度 = EMBEDDING_DIM（默认 1024）
    """
    if not texts:
        return []

    # BGE 模型建议对 query 文本添加前缀以提升检索质量
    # 参考: https://huggingface.co/BAAI/bge-m3
    prefixed = []
    for t in texts:
        # 短文本（≤32 字符）视为关键词/查询，添加查询前缀
        if len(t) <= 32:
            prefixed.append(f"Represent this sentence for searching relevant passages: {t}")
        else:
            prefixed.append(t)

    response = _get_embedding_client().embeddings.create(
        model=EMBEDDING_MODEL,
        input=prefixed,
    )
    # API 返回的向量通常已 L2 归一化
    return [item.embedding for item in response.data]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    计算两个向量的余弦相似度。

    注意：BGE-M3 通过 API 返回的向量通常已 L2 归一化，
    此时余弦相似度等同于向量点积，可简化为 sum(a[i]*b[i])。
    这里保留完整计算以兼容未归一化的场景。
    """
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def compute_skill_overlap_score(
    jd_keywords: list[str],
    candidate_skills: list[str],
) -> float:
    """
    计算 JD 要求技能与候选人技能的匹配度（基于关键词精确 + 子串匹配）。

    两阶段匹配：
      1. 精确匹配 + 子串匹配：候选人技能直接包含 JD 关键词
      2. 未命中则为 0（向量语义匹配需在 Agent 节点中异步调用 embed_texts）

    参数:
        jd_keywords: JD 要求的技能关键词
        candidate_skills: 候选人简历中的技能列表

    返回:
        匹配度分数 0.0-1.0
    """
    if not jd_keywords or not candidate_skills:
        return 0.0

    jd_lower = [k.lower() for k in jd_keywords]
    cand_lower = [s.lower() for s in candidate_skills]

    matched_count = 0
    for jd_skill in jd_lower:
        for cand_skill in cand_lower:
            if jd_skill == cand_skill or jd_skill in cand_skill or cand_skill in jd_skill:
                matched_count += 1
                break

    return matched_count / len(jd_keywords)


def _compute_keyword_skill_matches(
    jd_keywords: list[str],
    candidate_skills: list[str],
) -> tuple[list[str], list[str]]:
    matched: list[str] = []
    missing: list[str] = []
    cand_pairs = [(skill, skill.lower()) for skill in candidate_skills]

    for jd_skill in jd_keywords:
        jd_lower = jd_skill.lower()
        is_matched = any(
            jd_lower == cand_lower or jd_lower in cand_lower or cand_lower in jd_lower
            for _, cand_lower in cand_pairs
        )
        if is_matched:
            matched.append(jd_skill)
        else:
            missing.append(jd_skill)

    return matched, missing


async def compute_semantic_skill_score(
    jd_keywords: list[str],
    candidate_skills: list[str],
) -> dict:
    """
    组合精确/子串匹配与 embedding 语义匹配，返回更丰富的技能命中结果。
    embedding 调用失败时自动降级到关键词匹配，保证流水线不中断。
    """
    if not jd_keywords or not candidate_skills:
        return {
            "overall_score": 0.0,
            "matched": [],
            "semantic_matched": [],
            "missing": jd_keywords or [],
        }

    matched, missing = _compute_keyword_skill_matches(jd_keywords, candidate_skills)
    semantic_matched: list[dict] = []

    if missing:
        try:
            texts = [*missing, *candidate_skills]
            vectors = await embed_texts(texts)
            jd_vectors = vectors[:len(missing)]
            candidate_vectors = vectors[len(missing):]

            for jd_skill, jd_vector in zip(missing, jd_vectors):
                best_skill = ""
                best_score = 0.0
                for candidate_skill, candidate_vector in zip(candidate_skills, candidate_vectors):
                    similarity = cosine_similarity(jd_vector, candidate_vector)
                    if similarity > best_score:
                        best_skill = candidate_skill
                        best_score = similarity

                if best_skill and best_score >= SEMANTIC_MATCH_THRESHOLD:
                    semantic_matched.append({
                        "jd_skill": jd_skill,
                        "candidate_skill": best_skill,
                        "similarity": round(best_score, 4),
                    })
        except Exception:
            semantic_matched = []

    semantic_hit_skills = {item["jd_skill"] for item in semantic_matched}
    final_missing = [skill for skill in missing if skill not in semantic_hit_skills]
    overall_score = (len(matched) + len(semantic_matched)) / len(jd_keywords)

    return {
        "overall_score": overall_score,
        "matched": matched,
        "semantic_matched": semantic_matched,
        "missing": final_missing,
    }
