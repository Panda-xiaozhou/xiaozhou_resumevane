"""
LangGraph 状态图 — Agent 流水线定义
===================================
将 6 个 Agent 节点串联为完整的简历筛选流水线：

    orchestrator ─→ parser ─→ matcher ─→ analyzer ─→ reporter ─→ approver ─→ END

关键设计决策：
  1. 当前采用顺序执行，优先保证共享状态写入稳定
  2. matcher → analyzer → reporter 的顺序不会影响业务正确性，只会影响总耗时
  3. 任一节点出现 error 时，后续节点通过各自的短路逻辑跳过

维护注意：
  - 新增节点时在此文件中 add_node + add_edge
  - 修改节点顺序时注意数据依赖关系
  - graph 编译为单例 resume_screening_graph，确保全局复用
"""
from langgraph.graph import StateGraph, END

from .state import AgentState
from .nodes.orchestrator import orchestrator_node
from .nodes.parser import parser_node
from .nodes.matcher import matcher_node
from .nodes.analyzer import analyzer_node
from .nodes.reporter import reporter_node
from .nodes.approver import approver_node


def build_graph() -> StateGraph:
    """
    构建并编译 Agent 流水线状态图。

    返回:
        编译后的 CompiledStateGraph，可直接调用 .ainvoke(initial_state)
    """
    workflow = StateGraph(AgentState)

    # ── 注册 6 个节点 ────────────────────────────────
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("parser", parser_node)
    workflow.add_node("matcher", matcher_node)
    workflow.add_node("analyzer", analyzer_node)
    workflow.add_node("reporter", reporter_node)
    workflow.add_node("approver", approver_node)

    # ── 定义节点间的流转边 ────────────────────────────
    workflow.set_entry_point("orchestrator")
    workflow.add_edge("orchestrator", "parser")

    # 这里不再直接并行 fan-out。当前 AgentState 的大多数字段都是单值通道，
    # matcher/analyzer 若并发回写整份 state，会触发 LangGraph 的
    # INVALID_CONCURRENT_GRAPH_UPDATE。后续若要恢复并行，需要先把共享状态拆分
    # 为可安全合并的子状态，或为相应字段定义 reducer。
    workflow.add_edge("parser", "matcher")
    workflow.add_edge("matcher", "analyzer")
    workflow.add_edge("analyzer", "reporter")

    # 报告完成 → 审批决策
    workflow.add_edge("reporter", "approver")

    # 审批完成 → 流水线结束
    workflow.add_edge("approver", END)

    return workflow.compile()


# 全局单例——整个应用共享同一个编译后的 Graph
resume_screening_graph = build_graph()
