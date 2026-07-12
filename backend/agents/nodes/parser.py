"""
简历解析 Agent（Parser）
========================
职责：将非结构化简历（PDF/Word）转换为结构化 JSON。

工作流程：
  1. 读取文件，根据扩展名调用 pdf_parser 或 docx_parser 提取纯文本
  2. 将文本（截断至 6000 字符）送给 DeepSeek LLM 做结构化提取
  3. LLM 返回 JSON，包含姓名、技能、学历、工作经历、项目经验等字段
  4. 置信度 < 0.2 时判定为无效简历，标记 error

输出 Schema：
  {
    "name": "张三",
    "email": "zhang@example.com",
    "phone": "138xxxx",
    "education": [{"school": "...", "degree": "...", "major": "...", "year": "..."}],
    "skills": ["Python", "FastAPI"],
    "work_experience": [{"company": "...", "title": "...", "duration": "...", "description": "..."}],
    "projects": [{"name": "...", "description": "...", "tech_stack": ["..."]}],
    "certifications": ["..."],
    "confidence": 0.85
  }

异常处理：
  - 文件不存在 → error
  - 不支持的文件格式 → error
  - PDF 文本提取为空或过短 → error
  - LLM 返回非 JSON → error
  - 置信度过低 → error

维护注意：
  - 新增文件格式支持时在 pdf_parser.py 添加解析函数，并在此节点的 ext 判断中增加分支
  - 截断长度 6000 字符是经验值，确保不超过 DeepSeek 单次输入的 token 上限
"""
import json
import os

from ..state import AgentState
from ...utils.deepseek_client import chat_completion
from ...utils.llm_helpers import clean_llm_json, parse_llm_json
from ...utils.pdf_parser import extract_text_from_pdf, extract_text_from_docx

# 解析 Agent 的 System Prompt
# 注意：要求输出纯粹 JSON，不要 markdown 代码块包裹（DeepSeek 有时会加 ```json）
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


async def parser_node(state: AgentState) -> AgentState:
    """
    简历解析节点——流水线第二个节点。

    执行逻辑：
      1. 检查文件是否存在
      2. 根据扩展名调用对应的文本提取器
      3. 检查提取文本是否足够长（≥50字符）
      4. 截断至 6000 字符送给 DeepSeek 做结构化提取
      5. 清理 LLM 返回中可能的 markdown 代码块标记
      6. 校验置信度
    """
    if state.get("error"):
        state["step"] = "parser_skipped"
        return state

    file_path = state.get("resume_file_path", "")

    # ── 第一步：文件文本提取 ────────────────────────
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

    # ── 第二步：文本有效性检查 ──────────────────────
    if not raw_text or len(raw_text) < 50:
        state["error"] = "简历文本内容过短，无法解析"
        state["step"] = "error"
        return state

    # ── 第三步：LLM 结构化提取 ─────────────────────
    # 截断过长文本，避免超出 Token 限制
    truncated = raw_text[:6000]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"请解析以下简历文本：\n\n{truncated}"},
    ]

    try:
        result = await chat_completion(
            messages=messages,
            temperature=0.1,
            max_tokens=2048,
            caller="parser_node",
        )
        parsed = parse_llm_json(result.content)
    except json.JSONDecodeError as e:
        state["error"] = f"解析结果 JSON 格式错误: {e}"
        state["step"] = "error"
        return state
    except Exception as e:
        state["error"] = f"LLM 调用失败: {e}"
        state["step"] = "error"
        return state

    # ── 第四步：置信度校验 ──────────────────────────
    # 置信度 < 0.2 意味着文件可能不是简历，或内容完全无法解析
    if parsed.get("confidence", 0) < 0.2:
        state["error"] = "简历解析置信度过低，可能不是有效简历"
        state["step"] = "error"
        return state

    state["parsed_resume"] = parsed
    state["step"] = "parser_done"
    return state
