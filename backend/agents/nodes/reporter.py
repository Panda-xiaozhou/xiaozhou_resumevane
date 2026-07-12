"""
报告生成 Agent（Reporter）
==========================
职责：汇总 matcher 的定量打分 + analyzer 的定性分析，生成一份
结构化的 Markdown 筛选报告。

报告结构：
  1. 候选人基本信息
  2. 匹配度 + 推荐等级
  3. 技能匹配（✅ 命中 / ❌ 缺失）
  4. 维度得分表格
  5. 亮点汇总
  6. 风险提示
  7. 综合意见

异常处理：
  如果 LLM 生成失败（JSON 解析错误等），使用 _fallback_report()
  基于已有数据拼装一份降级报告，确保后续节点不会因报告缺失而中断。

维护注意：
  - 报告模板变更时同时更新 _fallback_report() 以保持一致
  - report_markdown 会被飞书消息卡片引用，注意长度控制在可读范围
"""
import json

from ..state import AgentState
from ...utils.deepseek_client import chat_completion
from ...utils.llm_helpers import clean_llm_json, parse_llm_json

SYSTEM_PROMPT = """你是一个招聘报告撰写专家。你需要将候选人的多维度分析结果汇总为一份简洁的 Markdown 摘要报告。

报告格式模板：

## 候选人筛选报告

**姓名**: {name}
**匹配度**: {score}/100
**推荐等级**: {recommend}

### 技能匹配
- ✅ 匹配技能: {matched}
- ❌ 缺失技能: {missing}

### 维度得分
| 维度 | 得分 |
|------|------|
| 硬技能 | xx |
| 学历 | xx |
| 经验 | xx |
| 项目 | xx |

### 亮点
- ...

### 风险
- ...

### 综合意见
一句话总结是否推荐面试及理由。

返回严格 JSON（不要 markdown 代码块包裹）：
{"report_markdown": "完整的 Markdown 报告文本", "title": "报告标题"}
"""


async def reporter_node(state: AgentState) -> AgentState:
    """
    报告生成节点——流水线第四节点。

    汇聚 matcher 和 analyzer 的输出，调用 LLM 生成格式化报告。
    如果上游节点已报错，跳过处理直接返回。
    """
    # 上游错误短路——不再生成报告
    if state.get("error"):
        state["step"] = "reporter_skipped"
        return state

    parsed = state.get("parsed_resume", {})

    # ── 构建 LLM 输入上下文 ──────────────────────────
    context = {
        "name": parsed.get("name", "未知"),
        "match_score": state.get("match_score", 0),
        "dimension_scores": state.get("dimension_scores", {}),
        "matched_keywords": state.get("matched_keywords", []),
        "missing_keywords": state.get("missing_keywords", []),
        "highlights": state.get("highlights", []),
        "risks": state.get("risks", []),
        "overall_flag": state.get("overall_flag", "yellow"),
    }

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"请根据以下数据生成筛选报告：\n\n{json.dumps(context, ensure_ascii=False, indent=2)}",
        },
    ]

    try:
        result = await chat_completion(
            messages=messages,
            temperature=0.3,
            max_tokens=2048,
            caller="reporter_node",
        )
        parsed = parse_llm_json(result.content)
        state["report_markdown"] = parsed.get("report_markdown", _fallback_report(state))
    except Exception:
        # 降级方案：直接拼装报告，不依赖 LLM 输出格式
        state["report_markdown"] = _fallback_report(state)

    state["step"] = "reporter_done"
    return state


def _fallback_report(state: AgentState) -> str:
    """
    降级报告生成——当 LLM 调用失败或返回格式错误时使用。
    直接基于 state 中已有数据拼装 Markdown，不依赖 LLM。

    维护注意：如果 SYSTEM_PROMPT 中的报告模板更新，这里也要同步更新。
    """
    parsed = state.get("parsed_resume", {})
    name = parsed.get("name", "未知")
    score = state.get("match_score", 0)
    highlights = state.get("highlights", [])
    risks = state.get("risks", [])
    matched = state.get("matched_keywords", [])
    missing = state.get("missing_keywords", [])
    dims = state.get("dimension_scores", {})

    hl_text = "\n".join(f"- {h.get('detail', h)}" for h in highlights) or "- 无"
    risk_text = "\n".join(f"- {r.get('detail', r)}" for r in risks) or "- 无"

    return f"""## 候选人筛选报告

**姓名**: {name}
**匹配度**: {score}/100

### 技能匹配
- ✅ 匹配: {", ".join(matched) if matched else "无"}
- ❌ 缺失: {", ".join(missing) if missing else "无"}

### 维度得分
| 维度 | 得分 |
|------|------|
| 硬技能 | {dims.get("hard_skill", "-")} |
| 学历 | {dims.get("education", "-")} |
| 经验 | {dims.get("experience", "-")} |
| 项目 | {dims.get("project", "-")} |

### 亮点
{hl_text}

### 风险
{risk_text}

### 综合意见
匹配度 {score}/100。请 HR 结合上述分析决定是否推进面试。
"""
