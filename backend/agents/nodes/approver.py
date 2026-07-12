"""
审批决策 Agent（Approver）
===========================
职责：根据匹配分和风险评级做出最终推荐决策。这是流水线的最后一个节点。

决策规则（阈值来自 config.py，可在环境变量中调整）：
  ┌──────────────────────────────────────────────────────────────┐
  │ match_score ≥ PASS_THRESHOLD(75) 且 overall_flag = "green"   │
  │   → 推荐（passed）：自动通过，触发飞书推送                      │
  │                                                              │
  │ match_score ≥ REVIEW_THRESHOLD(60) 且 overall_flag ≠ "red"   │
  │   → 待定（pending_review）：进入 HR 人工看板                  │
  │                                                              │
  │ 其他                                                         │
  │   → 不推荐（rejected）：静默归档                             │
  └──────────────────────────────────────────────────────────────┘

注意：
  - 此节点不做 LLM 调用，纯基于规则的确定性决策
  - 如需支持更复杂的决策逻辑（如不同岗位不同阈值），在 config 中扩展
  - 决策结果会写入 state["recommend"] 和 state["decision_reason"]，
    并在 application_service 中映射到 Application.status

维护注意：
  - 修改阈值或决策逻辑时同步更新 config.py 中的默认值
  - decision_reason 会显示在飞书卡片和 HR 看板，措辞保持简洁
"""
from ..state import AgentState
from ...config import PASS_THRESHOLD, REVIEW_THRESHOLD


async def approver_node(state: AgentState) -> AgentState:
    """
    审批决策节点——流水线最后节点。

    纯规则决策，不调用 LLM——保证决策结果确定性，避免 LLM 随机性影响。
    如果上游节点已报错，跳过决策直接返回。
    """
    # 上游错误短路——不做审批决策
    if state.get("error"):
        state["step"] = "approver_skipped"
        return state

    score = state.get("match_score", 0)
    flag = state.get("overall_flag", "yellow")

    # ── 三级决策 ─────────────────────────────────────
    if score >= PASS_THRESHOLD and flag == "green":
        # 高分 + 无风险 → 自动推荐
        state["recommend"] = "推荐"
        state["decision_reason"] = (
            f"匹配度 {score} 分（阈值 {PASS_THRESHOLD}），综合评级绿色，自动通过"
        )
    elif score >= REVIEW_THRESHOLD and flag != "red":
        # 中等分 或 有风险信号 → 待人工复审
        state["recommend"] = "待定"
        state["decision_reason"] = (
            f"匹配度 {score} 分（阈值 {REVIEW_THRESHOLD}），"
            f"综合评级 {flag}，建议人工复审"
        )
    else:
        # 低分 或 存在明显风险 → 不推荐
        state["recommend"] = "不推荐"
        state["decision_reason"] = (
            f"匹配度 {score} 分，综合评级 {flag}，暂不推荐"
        )

    state["step"] = "approver_done"
    return state
