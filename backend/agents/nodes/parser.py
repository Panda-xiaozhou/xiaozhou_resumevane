"""
简历解析 Agent（Parser）
========================
职责：将非结构化简历（PDF/Word）转换为结构化 JSON。
"""
import json
import os
import re

from ..state import AgentState
from ...utils.deepseek_client import chat_completion
from ...utils.llm_helpers import clean_llm_json, parse_llm_json
from ...utils.pdf_parser import extract_text_from_docx, extract_text_from_pdf

SYSTEM_PROMPT = """你是一个简历解析专家。从给出的简历文本中提取以下结构化字段。

返回严格 JSON（不要 markdown 代码块包裹）：
{
  "name": "姓名",
  "email": "邮箱",
  "phone": "电话",
  "education": [{"school": "学校", "degree": "学历", "major": "专业", "year": "毕业年份"}],
  "skills": ["技能1", "技能2"],
  "work_experience": [{"company": "公司", "title": "职位", "duration": "时间段", "description": "工作描述"}],
  "projects": [{"name": "项目名", "description": "描述", "tech_stack": ["技术"]}],
  "certifications": ["证书/奖项"],
  "confidence": 0.0-1.0
}

规则：
- 字段为空时用空数组 [] 或空字符串 ""
- confidence 表示信息完整度：所有字段都有值为 1.0，缺失关键字段（姓名/技能）扣分
- 如果文本不是简历或无法解析，confidence 设为 0，其他字段留空"""

JSON_REPAIR_PROMPT = """你是一个 JSON 修复器。请把收到的内容修复为严格合法的 JSON。
要求：
1. 只输出 JSON
2. 不要输出解释
3. 保持字段语义不变
4. 字段缺失时保留空数组或空字符串
"""


def _extract_first_match(patterns: list[str], text: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _fallback_resume_parse(raw_text: str, jd_keywords: list[str]) -> dict:
    email = _extract_first_match(
        [
            r"email[:：]\s*([^\s]+@[^\s]+)",
            r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
        ],
        raw_text,
    )
    phone = _extract_first_match(
        [
            r"phone[:：]\s*([0-9+\-\s]{7,})",
            r"(1[3-9]\d{9})",
        ],
        raw_text,
    )
    name = _extract_first_match(
        [
            r"name[:：]\s*([^\n\r]+)",
            r"姓名[:：]\s*([^\n\r]+)",
        ],
        raw_text,
    )

    matched_skills = []
    raw_text_lower = raw_text.lower()
    for keyword in jd_keywords:
        if keyword and keyword.lower() in raw_text_lower:
            matched_skills.append(keyword)

    if not matched_skills:
        skill_line = _extract_first_match(
            [
                r"skills?[:：]\s*([^\n\r]+)",
                r"技能[:：]\s*([^\n\r]+)",
            ],
            raw_text,
        )
        if skill_line:
            matched_skills = [item.strip() for item in re.split(r"[,，、/|]", skill_line) if item.strip()]

    confidence = 0.0
    if name:
        confidence += 0.15
    if email:
        confidence += 0.2
    if phone:
        confidence += 0.15
    if matched_skills:
        confidence += 0.25
    if len(raw_text) >= 200:
        confidence += 0.1

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "education": [],
        "skills": matched_skills,
        "work_experience": [],
        "projects": [],
        "certifications": [],
        "confidence": round(min(confidence, 0.6), 2),
    }


async def parser_node(state: AgentState) -> AgentState:
    if state.get("error"):
        state["step"] = "parser_skipped"
        return state

    file_path = state.get("resume_file_path", "")
    if not os.path.exists(file_path):
        state["error"] = f"文件不存在: {file_path}"
        state["step"] = "error"
        return state

    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        raw_text = extract_text_from_pdf(file_path)
    elif ext in (".docx", ".doc"):
        raw_text = extract_text_from_docx(file_path)
    else:
        state["error"] = f"不支持的文件格式: {ext}"
        state["step"] = "error"
        return state

    if not raw_text or len(raw_text) < 50:
        state["error"] = "简历文本内容过短，无法解析"
        state["step"] = "error"
        return state

    truncated = raw_text[:6000]
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"请解析以下简历文本：\n\n{truncated}"},
    ]

    parsed = None
    try:
        result = await chat_completion(
            messages=messages,
            temperature=0.1,
            max_tokens=2048,
            caller="parser_node",
        )
        parsed = parse_llm_json(result.content)
    except json.JSONDecodeError as error:
        cleaned_content = clean_llm_json(result.content)

        try:
            repair_result = await chat_completion(
                messages=[
                    {"role": "system", "content": JSON_REPAIR_PROMPT},
                    {"role": "user", "content": cleaned_content},
                ],
                temperature=0,
                max_tokens=2048,
                caller="parser_node_json_repair",
            )
            parsed = parse_llm_json(repair_result.content)
        except Exception:
            try:
                retry_result = await chat_completion(
                    messages=messages,
                    temperature=0,
                    max_tokens=2048,
                    caller="parser_node_retry",
                )
                parsed = parse_llm_json(retry_result.content)
            except Exception:
                parsed = _fallback_resume_parse(raw_text, state.get("jd_keywords", []))
                if parsed.get("confidence", 0) < 0.2:
                    state["error"] = f"解析结果 JSON 格式错误: {error}"
                    state["step"] = "error"
                    return state
    except Exception as error:
        state["error"] = f"LLM 调用失败: {error}"
        state["step"] = "error"
        return state

    if parsed.get("confidence", 0) < 0.2:
        fallback_parsed = _fallback_resume_parse(raw_text, state.get("jd_keywords", []))
        if fallback_parsed.get("confidence", 0) > parsed.get("confidence", 0):
            parsed = fallback_parsed

        if parsed.get("confidence", 0) < 0.2:
            state["error"] = "简历解析置信度过低，可能不是有效简历"
            state["step"] = "error"
            return state

    state["parsed_resume"] = parsed
    state["step"] = "parser_done"
    return state
