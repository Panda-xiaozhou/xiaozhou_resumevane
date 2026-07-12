"""
亮点/风险分析 Agent（Analyzer）
================================
职责：识别简历中的加分项和风险信号，输出综合评级。

亮点检测维度：
  - 大厂经历：BAT、TMD、FAANG 等知名企业实习/工作
  - 开源贡献：GitHub 高 Star 项目、知名项目 Contributor
  - 竞赛奖项：ACM、Kaggle、数学建模等
  - 技术影响力：技术博客、公众号、专利、论文
  - 专业认证：AWS/GCP/Azure 等云厂商认证

风险检测维度：
  - 频繁跳槽：平均每份工作时长 < 1 年
  - 工作断层：时间线存在明显空档且无合理解释
  - 技能夸大：声称的技能与项目经验不匹配
  - 学历存疑：学校或学历信息模糊
  - 内容过简：简历信息量过少

综合评级：
  - green: 无明显风险，有 1+ 亮点
  - yellow: 存在需要关注的信号
  - red: 存在明显风险或重大疑虑

注意：此节点的输出直接影响审批决策——green + 高分 = 自动通过；
red = 直接不推荐。确保分析标准一致。
"""
import json

from ..state import AgentState
from ...utils.deepseek_client import chat_completion
from ...utils.llm_helpers import clean_llm_json, parse_llm_json

SYSTEM_PROMPT = """你是一个资深招聘专家，专门负责识别候选人简历中的亮点和潜在风险。

## 亮点检测
- 大厂实习/工作经历（如 BAT、TMD、FAANG）
- 开源贡献（GitHub 高 Star 项目、知名项目 Contributor）
- 竞赛奖项（ACM、Kaggle、数学建模等）
- 技术博客或公众号
- 专利、论文发表
- 证书（如 AWS/Google 专业认证）

## 风险检测
- 频繁跳槽（平均每份工作时长 < 1 年）
- 工作经历时间线冲突或断层
- 技能描述与实际项目经验不匹配
- 学历信息存疑
- 简历内容过于简略或夸大

## 整体评级
- green: 无明显风险，有亮点
- yellow: 存在一些需关注的信号
- red: 存在明显风险或重大疑虑

返回严格 JSON（不要 markdown 代码块包裹）：

{
  "highlights": [{"type": "类型", "detail": "具体描述"}],
  "risks": [{"type": "类型", "severity": "high|medium|low", "detail": "具体描述"}],
  "overall_flag": "green|yellow|red"
}"""


async def analyzer_node(state: AgentState) -> AgentState:
    """
    分析节点——流水线第三节点（与 matcher 并行）。

    与 matcher 互不依赖：matcher 做定量匹配打分，analyzer 做定性分析。
    两者结果在 reporter 中汇总。
    """
    # 上游错误短路——避免在 parser 失败后浪费 LLM 调用
    if state.get("error"):
        state["step"] = "analyzer_skipped"
        return state

    parsed = state.get("parsed_resume", {})

    # ── 前置检查 ─────────────────────────────────────
    if not parsed:
        state["error"] = "缺少简历解析数据"
        state["step"] = "error"
        return state

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"请分析以下候选人的简历数据：\n\n{json.dumps(parsed, ensure_ascii=False, indent=2)}",
        },
    ]

    # ── LLM 调用 ─────────────────────────────────────
    try:
        result = await chat_completion(
            messages=messages,
            temperature=0.1,
            max_tokens=1024,
            caller="analyzer_node",
        )
        parsed = parse_llm_json(result.content)
    except Exception as e:
        state["error"] = f"亮点分析失败: {e}"
        state["step"] = "error"
        return state

    # ── 写入状态 ─────────────────────────────────────
    state["highlights"] = parsed.get("highlights", [])
    state["risks"] = parsed.get("risks", [])
    state["overall_flag"] = parsed.get("overall_flag", "yellow")
    state["step"] = "analyzer_done"
    return state
