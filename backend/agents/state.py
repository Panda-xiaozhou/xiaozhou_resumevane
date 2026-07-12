"""
AgentState — LangGraph 共享状态定义
===================================
整个 Agent 流水线共享同一个状态对象，各节点读取/写入对应字段。
LangGraph 通过 TypedDict 定义状态结构，用 Annotated[list, add_messages]
实现消息的增量追加（而非替换）。

字段按处理阶段分组：初始输入 → 解析结果 → 匹配结果 → 分析结果 → 报告 → 决策

维护注意：
  - 新增字段时确保在 application_service.run_screening_pipeline() 的
    initial_state 中提供默认值
  - 字段名与 nodes 中的读写一致，不要随意改名
"""
from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # ── 初始输入（由 application_service 填充）────────────
    # 投递记录 ID，用于关联数据库
    application_id: str
    # 关联的岗位 ID
    job_id: str
    # 岗位 JD 完整文本
    jd_text: str
    # JD 关键技能词列表
    jd_keywords: list[str]
    # 匹配权重配置 {"hard_skill": 0.4, "education": 0.2, ...}
    match_config: dict[str, float]
    # 候选人上传的简历文件在服务器上的绝对路径
    resume_file_path: str

    # ── 解析阶段输出 ─────────────────────────────────────
    # parser_node 输出: {"name", "email", "skills":[], "education":[], ...}
    parsed_resume: dict[str, Any]

    # ── 匹配阶段输出 ─────────────────────────────────────
    # 综合匹配分数 (0-100)
    match_score: float
    # 各维度得分: {"hard_skill": 90, "education": 80, ...}
    dimension_scores: dict[str, float]
    # 候选人命中 JD 要求的技能
    matched_keywords: list[str]
    # JD 要求但候选人缺乏的技能
    missing_keywords: list[str]

    # ── 分析阶段输出 ─────────────────────────────────────
    # 亮点列表: [{"type": "开源贡献", "detail": "..."}]
    highlights: list[dict[str, Any]]
    # 风险列表: [{"type": "频繁跳槽", "severity": "high", "detail": "..."}]
    risks: list[dict[str, Any]]
    # 综合评级: green(安全) / yellow(需关注) / red(有风险)
    overall_flag: str

    # ── 报告阶段输出 ─────────────────────────────────────
    # Markdown 格式的筛选摘要报告
    report_markdown: str

    # ── 决策阶段输出 ─────────────────────────────────────
    # 推荐结论: "推荐" / "待定" / "不推荐"
    recommend: str
    # 决策理由（一句话，展示在飞书卡片和 HR 看板）
    decision_reason: str

    # ── 运行时字段 ───────────────────────────────────────
    # LangGraph 消息历史，add_messages 注解确保每次追加而非覆盖
    messages: Annotated[list, add_messages]
    # 当前流水线步骤: start → orchestrator_done → parser_done → ...
    step: str
    # 错误信息，非空表示流水线中断
    error: str
