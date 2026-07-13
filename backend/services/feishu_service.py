"""
飞书推送服务
============
封装飞书开放平台 API：Token 管理、文件上传、消息卡片发送。

工作流程：
  1. 获取 tenant_access_token（自动刷新，提前 60s 刷新）
  2. 上传筛选报告 PDF 到飞书 → 获取 file_key
  3. 构建消息卡片模板 → 发送到指定群聊/用户

异常处理策略：
  - Token 获取失败 → 抛出 RuntimeError（不可恢复）
  - 文件上传失败 → 降级为纯文本卡片（不含附件链接）
  - 消息发送失败 → 返回 False，调用方标记 push_status = "failed"

配置依赖：
  - FEISHU_APP_ID / FEISHU_APP_SECRET: 飞书自建应用凭证（必填）
  - FEISHU_CHAT_ID: 推送目标群聊 ID，为空时不推送

维护注意：
  - 飞书 API 有频率限制（tenant_access_token: 限频，消息: 5次/秒/应用）
  - 生产环境建议使用 lark-oapi 官方 SDK 而非 httpx 直调（更完善的错误处理）
  - 消息卡片 JSON 格式参考飞书文档: https://open.feishu.cn/document/uAjLw4CM/ukzMukzMukzM/feishu-cards/card-components
"""
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime

import httpx

from ..config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_CHAT_ID, FRONTEND_BASE_URL


@dataclass
class FeishuSendResult:
    """飞书接口调用结果，统一承载消息发送和文件上传的诊断信息。"""

    stage: str
    ok: bool
    code: int | None = None
    msg: str = ""
    log_id: str = ""
    message_id: str = ""
    file_key: str = ""
    status_code: int | None = None

    def __bool__(self) -> bool:
        return self.ok

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "ok": self.ok,
            "code": self.code,
            "msg": self.msg,
            "log_id": self.log_id,
            "message_id": self.message_id,
            "file_key": self.file_key,
            "status_code": self.status_code,
        }


def _parse_feishu_result(stage: str, data: dict, status_code: int | None = None) -> FeishuSendResult:
    if not isinstance(data, dict):
        return FeishuSendResult(
            stage=stage,
            ok=False,
            msg="飞书响应不是有效 JSON 对象",
            status_code=status_code,
        )
    error = data.get("error") if isinstance(data, dict) else {}
    payload = data.get("data") if isinstance(data, dict) else {}
    if not isinstance(error, dict):
        error = {}
    if not isinstance(payload, dict):
        payload = {}

    return FeishuSendResult(
        stage=stage,
        ok=data.get("code") == 0,
        code=data.get("code"),
        msg=data.get("msg", ""),
        log_id=error.get("log_id", ""),
        message_id=payload.get("message_id", ""),
        file_key=payload.get("file_key", ""),
        status_code=status_code,
    )


def _exception_result(stage: str, exc: Exception) -> FeishuSendResult:
    return FeishuSendResult(stage=stage, ok=False, msg=str(exc) or exc.__class__.__name__)


def build_feishu_error_message(results: list[FeishuSendResult | dict]) -> str:
    """把失败的飞书调用压缩成 HR 可读的错误说明。"""
    messages = []
    for result in results:
        if isinstance(result, FeishuSendResult):
            if result.ok:
                continue
            stage = result.stage
            code = result.code
            msg = result.msg
            log_id = result.log_id
        else:
            stage = result.get("stage", "unknown")
            code = result.get("code")
            msg = result.get("msg", "")
            log_id = result.get("log_id", "")

        parts = [f"阶段: {stage}"]
        if code is not None:
            parts.append(f"错误码: {code}")
        if msg:
            parts.append(f"信息: {msg}")
        if log_id:
            parts.append(f"log_id: {log_id}")
        messages.append("；".join(parts))

    return "\n".join(messages)


def _truncate_text(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _extract_detail(item) -> str:
    if isinstance(item, dict):
        return str(item.get("detail") or item.get("type") or "").strip()
    return str(item or "").strip()


def _bullet_lines(items, max_items: int, empty_text: str = "暂无") -> str:
    lines = [
        f"- {_truncate_text(detail, 80)}"
        for detail in (_extract_detail(item) for item in (items or [])[:max_items])
        if detail
    ]
    return "\n".join(lines) if lines else f"- {empty_text}"


def _keyword_summary(keywords: list[str], max_items: int) -> str:
    values = [str(keyword).strip() for keyword in (keywords or []) if str(keyword).strip()]
    if not values:
        return "暂无"
    visible = "、".join(values[:max_items])
    if len(values) > max_items:
        return f"{visible} 等 {len(values)} 项"
    return visible


def _format_score(score: float) -> str:
    try:
        return f"{round(float(score), 1):g}"
    except (TypeError, ValueError):
        return "0"


def _format_created_at(value: str) -> str:
    if not value:
        return "-"
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value


def _build_detail_url(detail_url: str, job_id: str, application_id: str) -> str:
    if detail_url:
        return detail_url
    if job_id and application_id:
        return f"{FRONTEND_BASE_URL}/admin/jobs/{job_id}?application_id={application_id}"
    if job_id:
        return f"{FRONTEND_BASE_URL}/admin/jobs/{job_id}"
    return f"{FRONTEND_BASE_URL}/admin"


class FeishuClient:
    """
    飞书 API 客户端。

    使用方式:
        client = FeishuClient()
        upload_result = await client.upload_file("/path/to/resume.pdf")
        card_result = await client.send_card(card_data)
        file_result = await client.send_file(upload_result.file_key)
    """

    def __init__(self):
        self.app_id = FEISHU_APP_ID
        self.app_secret = FEISHU_APP_SECRET
        # 推送目标：群聊 chat_id，为空不推送
        self.chat_id = FEISHU_CHAT_ID
        # Token 缓存
        self._token: str = ""
        # Token 过期时间戳（Unix 秒）
        self._token_expire: float = 0

    async def _get_token(self) -> str:
        """
        获取 tenant_access_token。
        缓存策略：有效期内复用，过期前 60 秒自动刷新。
        飞书 token 有效期 2 小时（7200 秒）。
        """
        if self._token and time.time() < self._token_expire - 60:
            return self._token

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"飞书 token 获取失败: {data.get('msg')}")

            self._token = data["tenant_access_token"]
            self._token_expire = time.time() + data.get("expire", 7200)
            return self._token

    async def upload_file(self, file_path: str, file_name: str = "resume_summary.pdf") -> FeishuSendResult:
        """
        上传文件到飞书。

        参数:
            file_path: 本地文件绝对路径
            file_name: 在飞书中显示的文件名
        返回:
            结构化结果，成功时包含 file_key
        """
        if not file_path or not os.path.isfile(file_path):
            return FeishuSendResult(
                stage="file_upload",
                ok=False,
                msg=f"简历文件不存在或不可读: {file_path or '-'}",
            )

        try:
            token = await self._get_token()
            async with httpx.AsyncClient() as client:
                with open(file_path, "rb") as f:
                    resp = await client.post(
                        "https://open.feishu.cn/open-apis/im/v1/files",
                        headers={"Authorization": f"Bearer {token}"},
                        files={"file": (file_name, f)},
                        data={"file_type": "pdf", "file_name": file_name},
                    )
                data = resp.json()
                return _parse_feishu_result("file_upload", data, resp.status_code)
        except Exception as exc:
            return _exception_result("file_upload", exc)

    async def send_card(self, card: dict, receive_id: str = "") -> FeishuSendResult:
        """
        发送消息卡片。

        参数:
            card: 消息卡片 JSON（飞书卡片模板格式）
            receive_id: 接收者 ID（chat_id 或 open_id），为空则用全局配置的 FEISHU_CHAT_ID
        返回:
            结构化发送结果
        """
        if not receive_id:
            receive_id = self.chat_id
        if not receive_id:
            return FeishuSendResult(stage="card", ok=False, msg="FEISHU_CHAT_ID 未配置")

        try:
            token = await self._get_token()
            body = {
                "receive_id": receive_id,
                "msg_type": "interactive",
                "content": json.dumps(card, ensure_ascii=False),
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                data = resp.json()
                return _parse_feishu_result("card", data, resp.status_code)
        except Exception as exc:
            return _exception_result("card", exc)

    async def send_file(self, file_key: str, file_name: str = "", receive_id: str = "") -> FeishuSendResult:
        """
        发送已上传的飞书文件消息。

        file_name 仅用于调用方日志语义，飞书发送文件消息实际依赖 file_key。
        """
        if not receive_id:
            receive_id = self.chat_id
        if not receive_id:
            return FeishuSendResult(stage="file_send", ok=False, msg="FEISHU_CHAT_ID 未配置")
        if not file_key:
            return FeishuSendResult(stage="file_send", ok=False, msg=f"缺少 file_key，无法发送文件: {file_name or '-'}")

        try:
            token = await self._get_token()
            body = {
                "receive_id": receive_id,
                "msg_type": "file",
                "content": json.dumps({"file_key": file_key}, ensure_ascii=False),
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                data = resp.json()
                return _parse_feishu_result("file_send", data, resp.status_code)
        except Exception as exc:
            return _exception_result("file_send", exc)


# ── 全局单例 ───────────────────────────────────────
_feishu = FeishuClient()


def get_feishu_client() -> FeishuClient:
    """获取飞书客户端单例"""
    return _feishu


def build_candidate_card(
    name: str,
    match_score: float,
    matched_skills: list[str],
    highlights: list[dict],
    report_md: str,
    detail_url: str = "",
    *,
    application_id: str = "",
    job_id: str = "",
    job_title: str = "",
    candidate_email: str = "",
    created_at: str = "",
    decision_reason: str = "",
    risks: list[dict] | None = None,
    missing_keywords: list[str] | None = None,
) -> dict:
    """
    构建飞书消息卡片 JSON。

    参数:
        name: 候选人姓名
        match_score: 匹配分数
        matched_skills: 命中的技能列表
        highlights: 亮点列表 [{"type": "大厂经历", "detail": "..."}]
        report_md: Markdown 格式的筛选报告
        detail_url: HR 查看候选人的前端页面地址
    返回:
        飞书消息卡片 JSON 字典，可直接传给 send_card()

    卡片结构：
        ┌──────────────────────────────────┐
        │  📋 新候选人通过筛选              │
        │                                  │
        │  👤 张三  |  匹配度：85/100       │
        │  ✅ 匹配：Python, React, FastAPI  │
        │  ⭐ 亮点：...                     │
        │  📎 点击查看筛选报告              │
        │  [查看详情] [联系候选人]          │
        └──────────────────────────────────┘
    """
    resolved_detail_url = _build_detail_url(detail_url, job_id, application_id)
    summary = (
        f"**候选人：{name or '未知'}**\n"
        f"岗位：{job_title or '未填写'}\n"
        f"邮箱：{candidate_email or '-'}\n"
        f"投递时间：{_format_created_at(created_at)}\n"
        f"匹配度：{_format_score(match_score)}/100"
    )
    decision = decision_reason or "匹配度和综合评级达到自动推荐标准。"
    skills = (
        f"**技能摘要**\n"
        f"命中：{_keyword_summary(matched_skills, 3)}\n"
        f"缺失：{_keyword_summary(missing_keywords or [], 3)}"
    )
    report_summary = _truncate_text(report_md, 180)

    elements = [
        {
            "tag": "markdown",
            "content": summary,
        },
        {
            "tag": "markdown",
            "content": f"**推荐理由**\n{_truncate_text(decision, 120)}",
        },
        {
            "tag": "markdown",
            "content": skills,
        },
        {
            "tag": "markdown",
            "content": f"**候选人亮点**\n{_bullet_lines(highlights, 3)}",
        },
        {
            "tag": "markdown",
            "content": f"**风险提示**\n{_bullet_lines(risks or [], 2, '未发现明显风险')}",
        },
    ]
    if report_summary:
        elements.append({
            "tag": "markdown",
            "content": f"**报告摘要**\n{report_summary}",
        })

    elements.append({
        "tag": "action",
        "actions": [
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "查看投递详情"},
                "type": "primary",
                "url": resolved_detail_url,
            },
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "进入 HR 看板"},
                "type": "default",
                "url": f"{FRONTEND_BASE_URL}/admin/dashboard",
            },
        ],
    })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "推荐候选人通过筛选"},
            "template": "green",
        },
        "elements": elements,
    }
