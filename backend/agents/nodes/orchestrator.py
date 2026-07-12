"""
调度 Agent（Orchestrator）
==========================
职责：作为流水线入口，做确定性的输入校验。
只检查岗位 JD 和简历文件路径是否可用，不再调用 LLM。
"""
import os

from ..state import AgentState


async def orchestrator_node(state: AgentState) -> AgentState:
    """
    轻量入口校验：
      1. application_id / job_id 存在
      2. jd_text 非空
      3. resume_file_path 非空且文件存在
    满足则放行到 parser，不满足则直接终止流水线。
    """
    application_id = state.get("application_id", "").strip()
    job_id = state.get("job_id", "").strip()
    jd_text = state.get("jd_text", "").strip()
    resume_file_path = state.get("resume_file_path", "").strip()

    if not application_id:
        state["error"] = "缺少 application_id"
        state["step"] = "error"
        return state

    if not job_id:
        state["error"] = "缺少 job_id"
        state["step"] = "error"
        return state

    if not jd_text:
        state["error"] = "缺少 JD 正文内容"
        state["step"] = "error"
        return state

    if not resume_file_path:
        state["error"] = "缺少简历文件路径"
        state["step"] = "error"
        return state

    if not os.path.exists(resume_file_path):
        state["error"] = f"简历文件不存在: {resume_file_path}"
        state["step"] = "error"
        return state

    state["step"] = "orchestrator_done"
    state["error"] = ""
    return state
