"""
亮点/风险分析 Agent（Analyzer）
==============================
职责：识别简历中的亮点和风险信号，输出综合评级。
"""
import json

from ..state import AgentState
from ...utils.deepseek_client import chat_completion
from ...utils.llm_helpers import parse_llm_json

SYSTEM_PROMPT = """你是一个资深招聘专家，专门负责识别候选人简历中的亮点和潜在风险。
返回严格 JSON（不要 markdown 代码块包裹）：
{
  "highlights": [{"type": "类型", "detail": "具体描述"}],
  "risks": [{"type": "类型", "severity": "high|medium|low", "detail": "具体描述"}],
  "overall_flag": "green|yellow|red"
}
"""


def _fallback_analyzer(parsed_resume: dict) -> dict:
    confidence = parsed_resume.get("confidence", 0) or 0
    skills = parsed_resume.get("skills", []) or []

    highlights = []
    risks = []
    overall_flag = "yellow"

    if len(skills) >= 3:
        highlights.append({
            "type": "技能覆盖",
            "detail": f"简历中提取到 {len(skills)} 项技能，可继续结合岗位要求评估。",
        })

    if confidence < 0.4:
        risks.append({
            "type": "解析置信度低",
            "severity": "high",
            "detail": f"简历解析置信度仅为 {confidence}，部分信息可能缺失或格式异常。",
        })
        overall_flag = "red"
    elif confidence < 0.7:
        risks.append({
            "type": "信息完整度一般",
            "severity": "medium",
            "detail": f"简历解析置信度为 {confidence}，建议结合人工复核判断结果。",
        })

    return {
        "highlights": highlights,
        "risks": risks,
        "overall_flag": overall_flag,
    }


async def analyzer_node(state: AgentState) -> AgentState:
    if state.get("error"):
        state["step"] = "analyzer_skipped"
        return state

    parsed_resume = state.get("parsed_resume", {})
    if not parsed_resume:
        state["error"] = "缺少简历解析数据"
        state["step"] = "error"
        return state

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"请分析以下候选人的简历数据：\n\n{json.dumps(parsed_resume, ensure_ascii=False, indent=2)}",
        },
    ]

    try:
        result = await chat_completion(
            messages=messages,
            temperature=0.1,
            max_tokens=1024,
            caller="analyzer_node",
        )
        parsed = parse_llm_json(result.content)
    except Exception:
        parsed = _fallback_analyzer(parsed_resume)

    state["highlights"] = parsed.get("highlights", [])
    state["risks"] = parsed.get("risks", [])
    state["overall_flag"] = parsed.get("overall_flag", "yellow")
    state["step"] = "analyzer_done"
    return state
