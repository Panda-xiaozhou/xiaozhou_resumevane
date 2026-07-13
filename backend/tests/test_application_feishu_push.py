import uuid
from pathlib import Path

import pytest

from backend.models.agent_result import AgentResult
from backend.models.application import Application
from backend.models.job import Job
from backend.models.user import Candidate
from backend.services.application_service import _try_push_to_feishu, push_selected_applications_to_feishu
from backend.services.feishu_service import FeishuSendResult


class _FakeQuery:
    def __init__(self, value):
        self.value = value

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.value


class _FakeDb:
    def __init__(self, candidate):
        self.candidate = candidate

    def query(self, model):
        return _FakeQuery(self.candidate)


class _FakeCollectionQuery:
    def __init__(self, values):
        self.values = values

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self.values


class _FakePushDb:
    def __init__(self, apps, jobs, results):
        self.apps = apps
        self.jobs = jobs
        self.results = results
        self.committed = False

    def query(self, model):
        if model is Application:
            return _FakeCollectionQuery(self.apps)
        if model is Job:
            return _FakeCollectionQuery(self.jobs)
        if model is AgentResult:
            return _FakeCollectionQuery(self.results)
        return _FakeCollectionQuery([])

    def commit(self):
        self.committed = True


class _FakeFeishuClient:
    def __init__(self, *, file_send_ok=True):
        self.file_send_ok = file_send_ok
        self.calls = []

    async def send_card(self, card):
        self.calls.append(("send_card", card))
        return FeishuSendResult(stage="card", ok=True, code=0, message_id="om_card")

    async def upload_file(self, file_path, file_name):
        self.calls.append(("upload_file", Path(file_path).name, file_name))
        return FeishuSendResult(stage="file_upload", ok=True, code=0, file_key="file_xxx")

    async def send_file(self, file_key, file_name):
        self.calls.append(("send_file", file_key, file_name))
        if self.file_send_ok:
            return FeishuSendResult(stage="file_send", ok=True, code=0, message_id="om_file")
        return FeishuSendResult(
            stage="file_send",
            ok=False,
            code=230002,
            msg="Bot/User can NOT be out of the chat.",
            log_id="log_xxx",
        )


def _make_context(resume_file: str):
    candidate_id = uuid.uuid4()
    job_id = uuid.uuid4()
    app = Application(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        job_id=job_id,
        resume_file=resume_file,
        form_data={"resume_original_name": "张三.pdf"},
    )
    job = Job(
        id=job_id,
        hr_user_id=uuid.uuid4(),
        title="后端开发工程师",
        jd_text="Python FastAPI",
    )
    candidate = Candidate(
        id=candidate_id,
        name="张三",
        email="zhangsan@example.com",
        phone="13800000000",
    )
    agent_result = AgentResult(
        application_id=app.id,
        agent_name="pipeline",
        status="completed",
        output_data={},
    )
    final_state = {
        "parsed_resume": {"name": "张三"},
        "match_score": 92,
        "matched_keywords": ["Python", "FastAPI"],
        "missing_keywords": ["Kubernetes"],
        "highlights": [{"detail": "有招聘系统经验"}],
        "risks": [],
        "decision_reason": "匹配度高",
        "report_markdown": "建议进入面试。",
    }
    return app, job, candidate, agent_result, final_state


@pytest.mark.asyncio
async def test_try_push_to_feishu_sends_card_then_pdf_file(monkeypatch, tmp_path):
    resume_file = tmp_path / "resume.pdf"
    resume_file.write_bytes(b"%PDF-1.4")
    app, job, candidate, agent_result, final_state = _make_context(str(resume_file))
    client = _FakeFeishuClient()
    monkeypatch.setattr("backend.services.feishu_service.get_feishu_client", lambda: client)

    await _try_push_to_feishu(_FakeDb(candidate), app, job, final_state, agent_result)

    assert [call[0] for call in client.calls] == ["send_card", "upload_file", "send_file"]
    assert app.push_status == "pushed"
    assert agent_result.output_data["feishu_push_results"][0]["stage"] == "card"
    assert agent_result.output_data["feishu_push_results"][1]["stage"] == "file_send"


@pytest.mark.asyncio
async def test_try_push_to_feishu_records_file_send_failure(monkeypatch, tmp_path):
    resume_file = tmp_path / "resume.pdf"
    resume_file.write_bytes(b"%PDF-1.4")
    app, job, candidate, agent_result, final_state = _make_context(str(resume_file))
    client = _FakeFeishuClient(file_send_ok=False)
    monkeypatch.setattr("backend.services.feishu_service.get_feishu_client", lambda: client)

    await _try_push_to_feishu(_FakeDb(candidate), app, job, final_state, agent_result)

    assert app.push_status == "failed"
    assert "230002" in agent_result.output_data["feishu_push_error"]
    assert "log_xxx" in agent_result.error_message


@pytest.mark.asyncio
async def test_push_selected_applications_reuses_latest_pipeline_result(monkeypatch, tmp_path):
    resume_file = tmp_path / "resume.pdf"
    resume_file.write_bytes(b"%PDF-1.4")
    app, job, candidate, agent_result, final_state = _make_context(str(resume_file))
    agent_result.output_data = final_state
    db = _FakePushDb([app], [job], [agent_result])
    calls = []

    async def fake_push(push_db, push_app, push_job, push_state, push_result):
        calls.append((push_app.id, push_job.id, push_state["match_score"], push_result.id))
        push_app.push_status = "pushed"

    monkeypatch.setattr("backend.services.application_service._try_push_to_feishu", fake_push)

    summary = await push_selected_applications_to_feishu(db, [str(app.id)], {job.id})

    assert calls == [(app.id, job.id, 92, agent_result.id)]
    assert summary["pushed_count"] == 1
    assert summary["failed_count"] == 0
    assert summary["missing_ids"] == []
    assert db.committed is True


@pytest.mark.asyncio
async def test_push_selected_applications_reports_missing_pipeline_result(tmp_path):
    resume_file = tmp_path / "resume.pdf"
    resume_file.write_bytes(b"%PDF-1.4")
    app, job, candidate, agent_result, final_state = _make_context(str(resume_file))
    db = _FakePushDb([app], [job], [])

    summary = await push_selected_applications_to_feishu(db, [str(app.id)], {job.id})

    assert app.push_status == "failed"
    assert summary["pushed_count"] == 0
    assert summary["failed_count"] == 1
    assert summary["results"][0]["reason"] == "缺少已完成筛选结果，无法推送"
