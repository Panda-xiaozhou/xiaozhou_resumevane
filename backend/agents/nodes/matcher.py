"""
技能匹配 Agent（Matcher）
=========================
职责：将候选人简历与岗位 JD 做多维度匹配打分。

四个评分维度（权重可配置）：
  - hard_skill（硬技能）：技术栈匹配度——JD 要求的技术是否出现在候选人的项目和技能列表中
  - education（学历）：学历层次是否满足 JD 要求
  - experience（工作经验）：工作年限和相关领域经验是否匹配
  - project（项目相关性）：候选人做过的项目与岗位的相关程度

每个维度 0-100 分，总分 = Σ(维度分 × 权重)。
默认权重: hard_skill: 0.4, education: 0.2, experience: 0.25, project: 0.15

输出：
  - match_score: 综合匹配分 (0-100)
  - dimension_scores: 各维度得分
  - matched_keywords: 命中 JD 要求的技能
  - missing_keywords: JD 要求但候选人缺乏的技能
  - match_detail: 一句话总结

注意：此 Agent 不调用结构化工具（如 calculate_match_score），而是完全
依赖 LLM 的理解能力做语义匹配——对于同义词（如 React.js ≈ React）和
隐含技能（如"构建 REST API"隐含 FastAPI/Flask 能力）更准确。
"""
import json

from ..state import AgentState
from ...utils.deepseek_client import chat_completion
from ...utils.llm_helpers import parse_llm_json
from ...utils.embedding import compute_semantic_skill_score

SYSTEM_PROMPT = """你是一个技术招聘的匹配评估专家。你需要将候选人简历与岗位 JD 做多维度匹配评分。

评分维度及说明：
- hard_skill (硬技能): 技术栈匹配度，JD 要求的技术是否出现在候选人技能/项目经验中
- education (学历): 学历是否符合 JD 要求
- experience (工作经验): 工作年限和相关领域经验是否匹配
- project (项目相关性): 候选人项目经验与岗位的相关程度

每个维度 0-100 分，总分按权重计算。

返回严格 JSON（不要 markdown 代码块包裹）：

{
  "match_score": 85,
  "dimension_scores": {"hard_skill": 90, "education": 80, "experience": 75, "project": 90},
  "matched_keywords": ["Python", "FastAPI", "React"],
  "missing_keywords": ["Docker", "Kubernetes"],
  "match_detail": "一句话总结匹配情况"
}

评分参考：
- 90-100: JD 要求绝大部分满足
- 75-89: 基本满足，个别要求不达标
- 60-74: 部分满足，存在较明显差距
- 60 以下: 差距较大"""


async def matcher_node(state: AgentState) -> AgentState:
    """
    技能匹配节点——流水线第三节点（与 analyzer 并行）。

    需要 parser 节点的结构化输出 + job 表中的 JD 信息。
    """
    # 上游错误短路——避免在 parser 失败后浪费 LLM 调用
    if state.get("error"):
        state["step"] = "matcher_skipped"
        return state

    parsed = state.get("parsed_resume", {})
    jd_text = state.get("jd_text", "")
    jd_keywords = state.get("jd_keywords", [])
    weights = state.get(
        "match_config",
        # 默认权重配置
        {"hard_skill": 0.4, "education": 0.2, "experience": 0.25, "project": 0.15},
    )

    # ── 前置检查 ─────────────────────────────────────
    if not parsed or not jd_text:
        state["error"] = "缺少简历解析数据或 JD 文本"
        state["step"] = "error"
        return state

    # ── 构建 LLM 输入 ────────────────────────────────
    # 将 JD、关键词、简历结构化数据、权重一起送入 LLM

    # 预计算技能重叠度（精确命中 + 语义命中）
    skill_match = await compute_semantic_skill_score(
        jd_keywords,
        parsed.get("skills", []),
    )
    all_matched_keywords = [
        *skill_match["matched"],
        *[item["jd_skill"] for item in skill_match["semantic_matched"]],
    ]
    semantic_match_lines = [
        f"{item['jd_skill']} -> {item['candidate_skill']} ({item['similarity']:.2f})"
        for item in skill_match["semantic_matched"]
    ]

    user_prompt = f"""## 岗位 JD
{jd_text[:3000]}

## JD 关键技能词
{json.dumps(jd_keywords, ensure_ascii=False)}

## 候选人简历（结构化）
{json.dumps(parsed, ensure_ascii=False, indent=2)}

## 评分权重
{json.dumps(weights, ensure_ascii=False)}

## 自动计算的技能重叠度
{skill_match["overall_score"]:.0%}

## 精确命中的 JD 技能
{json.dumps(skill_match["matched"], ensure_ascii=False)}

## 语义命中的 JD 技能
{json.dumps(semantic_match_lines, ensure_ascii=False)}

## 当前仍缺失的 JD 技能
{json.dumps(skill_match["missing"], ensure_ascii=False)}

请按上述维度进行匹配打分。"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    # ── LLM 调用 ─────────────────────────────────────
    try:
        result = await chat_completion(
            messages=messages,
            temperature=0.1,
            max_tokens=1024,
            caller="matcher_node",
        )
        parsed = parse_llm_json(result.content)
    except Exception as e:
        state["error"] = f"匹配评分失败: {e}"
        state["step"] = "error"
        return state

    # ── 写入状态 ─────────────────────────────────────
    state["match_score"] = parsed.get("match_score", 0)
    state["dimension_scores"] = parsed.get("dimension_scores", {})
    llm_matched = parsed.get("matched_keywords", [])
    llm_missing = parsed.get("missing_keywords", [])
    state["matched_keywords"] = list(dict.fromkeys([*all_matched_keywords, *llm_matched]))
    state["missing_keywords"] = [
        skill for skill in llm_missing if skill not in state["matched_keywords"]
    ]
    state["step"] = "matcher_done"
    return state
