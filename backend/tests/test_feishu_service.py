import json

import pytest

from backend.services.feishu_service import (
    FeishuClient,
    build_candidate_card,
    build_feishu_error_message,
)


class _FakeResponse:
    def __init__(self, data: dict, status_code: int = 200):
        self._data = data
        self.status_code = status_code

    def json(self) -> dict:
        return self._data


class _FakeAsyncClient:
    posts = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, headers=None, json=None, files=None, data=None):
        self.posts.append(
            {
                "url": url,
                "headers": headers or {},
                "json": json,
                "files": files,
                "data": data,
            }
        )
        if url.endswith("/im/v1/files"):
            return _FakeResponse({"code": 0, "msg": "success", "data": {"file_key": "file_xxx"}})
        return _FakeResponse({"code": 0, "msg": "success", "data": {"message_id": "om_xxx"}})


@pytest.fixture(autouse=True)
def reset_fake_client():
    _FakeAsyncClient.posts = []
    yield


def test_build_candidate_card_includes_job_context_deep_link_and_screening_summary():
    card = build_candidate_card(
        name="张三",
        match_score=91,
        matched_skills=["Python", "FastAPI", "Vue", "Docker"],
        highlights=[
            {"type": "项目经验", "detail": "主导过招聘系统重构"},
            {"type": "工程能力", "detail": "有完整后端服务经验"},
            {"type": "协作", "detail": "跨团队沟通稳定"},
            {"type": "额外亮点", "detail": "不应展示第四条"},
        ],
        report_md="## 筛选报告\n候选人和岗位匹配度高，建议进入面试。",
        application_id="app-1",
        job_id="job-1",
        job_title="后端开发工程师",
        candidate_email="zhangsan@example.com",
        created_at="2026-07-13T12:00:00",
        decision_reason="匹配度高且综合风险低",
        risks=[{"type": "经验年限", "detail": "大型团队经验偏少"}],
        missing_keywords=["Kubernetes"],
        detail_url="http://localhost:3000/admin/jobs/job-1?application_id=app-1",
    )

    content = "\n".join(
        element.get("content", "")
        for element in card["elements"]
        if element.get("tag") == "markdown"
    )
    action = next(element for element in card["elements"] if element["tag"] == "action")

    assert card["header"]["title"]["content"] == "推荐候选人通过筛选"
    assert "张三" in content
    assert "后端开发工程师" in content
    assert "zhangsan@example.com" in content
    assert "匹配度：91/100" in content
    assert "匹配度高且综合风险低" in content
    assert "主导过招聘系统重构" in content
    assert "大型团队经验偏少" in content
    assert "Docker" not in content
    assert "不应展示第四条" not in content
    assert "Kubernetes" in content
    assert action["actions"][0]["url"].endswith("/admin/jobs/job-1?application_id=app-1")


@pytest.mark.asyncio
async def test_send_card_returns_structured_message_result(monkeypatch):
    monkeypatch.setattr("backend.services.feishu_service.httpx.AsyncClient", _FakeAsyncClient)
    client = FeishuClient()
    client.chat_id = "oc_xxx"
    client._token = "token"
    client._token_expire = 9_999_999_999

    result = await client.send_card({"elements": []})

    assert result.ok is True
    assert result.code == 0
    assert result.message_id == "om_xxx"
    payload = _FakeAsyncClient.posts[-1]["json"]
    assert payload["receive_id"] == "oc_xxx"
    assert payload["msg_type"] == "interactive"
    assert json.loads(payload["content"]) == {"elements": []}


@pytest.mark.asyncio
async def test_send_card_wraps_token_exception_as_structured_failure(monkeypatch):
    client = FeishuClient()
    client.chat_id = "oc_xxx"

    async def raise_token_error():
        raise RuntimeError("飞书 token 获取失败: bad app secret")

    monkeypatch.setattr(client, "_get_token", raise_token_error)

    result = await client.send_card({"elements": []})

    assert result.ok is False
    assert result.stage == "card"
    assert "bad app secret" in result.msg


@pytest.mark.asyncio
async def test_upload_file_and_send_file_return_structured_results(monkeypatch, tmp_path):
    monkeypatch.setattr("backend.services.feishu_service.httpx.AsyncClient", _FakeAsyncClient)
    client = FeishuClient()
    client.chat_id = "oc_xxx"
    client._token = "token"
    client._token_expire = 9_999_999_999
    resume_path = tmp_path / "resume.pdf"
    resume_path.write_bytes(b"%PDF-1.4")

    upload_result = await client.upload_file(str(resume_path), "candidate.pdf")
    send_result = await client.send_file(upload_result.file_key, "candidate.pdf")

    assert upload_result.ok is True
    assert upload_result.file_key == "file_xxx"
    assert send_result.ok is True
    payload = _FakeAsyncClient.posts[-1]["json"]
    assert payload["msg_type"] == "file"
    assert json.loads(payload["content"]) == {"file_key": "file_xxx"}


def test_upload_file_reports_missing_local_file():
    client = FeishuClient()

    result = asyncio_run(client.upload_file("missing.pdf", "missing.pdf"))

    assert result.ok is False
    assert result.stage == "file_upload"
    assert "不存在" in result.msg


def asyncio_run(awaitable):
    import asyncio

    return asyncio.run(awaitable)


def test_build_feishu_error_message_keeps_stage_code_msg_and_log_id():
    message = build_feishu_error_message(
        [
            {
                "stage": "card",
                "code": 230002,
                "msg": "Bot/User can NOT be out of the chat.",
                "log_id": "log_xxx",
            }
        ]
    )

    assert "card" in message
    assert "230002" in message
    assert "Bot/User can NOT be out of the chat." in message
    assert "log_xxx" in message
