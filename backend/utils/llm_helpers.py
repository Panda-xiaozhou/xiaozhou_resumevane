"""
LLM 响应处理工具
================
提供 LLM 返回内容的通用处理函数，所有 Agent 节点共用。
"""
import json
import re


def clean_llm_json(content: str) -> str:
    """
    清理 LLM 返回内容中可能包裹的 markdown 代码块标记，提取纯 JSON 文本。

    安全处理以下所有情况：
      - ```json\\n{...}\\n```   （标准多行包裹）
      - ```\\n{...}\\n```       （无语言标识）
      - ```json{...}```         （无换行，全在一行）
      - ```{...}```             （裸标记，内容同行）
      - ```                     （仅有开头标记，内容缺换行）
      - 纯 JSON 文本，无任何包裹

    参数:
        content: LLM 原始返回字符串
    返回:
        去除代码块标记后的纯 JSON 文本
    """
    text = content.strip()

    # 以 ``` 开头 —— 尝试移除代码块包裹
    if text.startswith("```"):
        # 去掉开头的 ``` 及可能紧跟的语言标识（如 ```json → 去掉前 3 个反引号及至换行/内容前的部分）
        text = text[3:]  # 去掉前 3 个反引号
        # 去掉可能的语言标识（"json", "javascript" 等），直到换行或遇到 {
        text = text.lstrip("jsonjavascript\n\r ")
        # 去掉尾部 ```
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    return text


def parse_llm_json(content: str) -> dict:
    """
    清理并解析 LLM 返回的 JSON。

    组合 clean_llm_json + json.loads，统一异常类型。

    参数:
        content: LLM 原始返回字符串
    返回:
        解析后的字典
    抛出:
        json.JSONDecodeError: JSON 格式无效
    """
    cleaned = clean_llm_json(content)
    candidates = [cleaned]

    # 如果前后混入了解释文本，尝试只截取最外层 JSON 对象
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
        candidates.append(cleaned[first_brace:last_brace + 1])

    last_error = None
    for candidate in candidates:
        normalized = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            return json.loads(normalized)
        except json.JSONDecodeError as error:
            last_error = error

    raise last_error if last_error else json.JSONDecodeError("Invalid JSON", cleaned, 0)
