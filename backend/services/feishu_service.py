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

import httpx

from ..config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_CHAT_ID, FRONTEND_BASE_URL


class FeishuClient:
    """
    飞书 API 客户端。

    使用方式:
        client = FeishuClient()
        file_key = await client.upload_file("/path/to/report.pdf")
        success = await client.send_card(card_data)
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

    async def upload_file(self, file_path: str, file_name: str = "resume_summary.pdf") -> str | None:
        """
        上传文件到飞书。

        参数:
            file_path: 本地文件绝对路径
            file_name: 在飞书中显示的文件名
        返回:
            file_key: 飞书文件标识，用于消息卡片引用；失败时返回 None
        """
        if not os.path.exists(file_path):
            return None

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
            if data.get("code") != 0:
                return None
            return data.get("data", {}).get("file_key")

    async def send_card(self, card: dict, receive_id: str = "") -> bool:
        """
        发送消息卡片。

        参数:
            card: 消息卡片 JSON（飞书卡片模板格式）
            receive_id: 接收者 ID（chat_id 或 open_id），为空则用全局配置的 FEISHU_CHAT_ID
        返回:
            True 表示发送成功，False 表示失败
        """
        if not receive_id:
            receive_id = self.chat_id
        if not receive_id:
            return False

        token = await self._get_token()
        body = {
            "receive_id": receive_id,
            "msg_type": "interactive",
            "content": json.dumps(card),
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
            return data.get("code") == 0


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
    # 亮点文本（最多显示 3 条，避免卡片过长）
    hl_text = "\n".join(
        f"• {h.get('detail', str(h))}" for h in (highlights or [])[:3]
    ) or "• 暂无"
    summary = f"**👤 候选人：{name}**\n📊 匹配度：{match_score}/100"
    if matched_skills:
        summary += f"\n✅ 匹配技能：{', '.join(matched_skills)}"

    elements = [
        {
            "tag": "markdown",
            "content": summary,
        },
        {
            "tag": "markdown",
            "content": f"⭐ **亮点**\n{hl_text}",
        },
    ]

    # 操作按钮
    if not detail_url:
        detail_url = f"{FRONTEND_BASE_URL}/admin"
    elements.append({
        "tag": "action",
        "actions": [
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "查看详情"},
                "type": "primary",
                "url": detail_url,
            }
        ],
    })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "📋 新候选人通过筛选"},
            "template": "green",
        },
        "elements": elements,
    }
