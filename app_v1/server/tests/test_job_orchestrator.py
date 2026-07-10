import asyncio
from types import SimpleNamespace

import pytest

from sdk.protocol.messages import parse_launcher_message
from app.service.job_orchestrator import JobOrchestrator, LauncherPolicyViolation
from app.service.job_service import JOB_PROGRESS_MAX_BYTES, JobService
from app.state import RuntimeRegistry


class FakeDb:
    def __init__(self):
        self.rollbacks = 0

    async def rollback(self):
        self.rollbacks += 1


@pytest.mark.asyncio
async def test_wait_for_answer_returns_connection_before_wait_and_cleans_event(monkeypatch):
    registry = RuntimeRegistry()
    orchestrator = JobOrchestrator(registry)
    db = FakeDb()
    queued = SimpleNamespace(id="job-1", answer=None, state="assigned")
    answered = SimpleNamespace(
        id="job-1",
        answer={"type": "answer", "sdp": "v=0\r\n"},
        state="answer_ready",
    )
    results = [queued, answered]

    async def get_job(_db, *, job_id, user_id=None):
        assert job_id == "job-1"
        assert user_id == "user-1"
        return results.pop(0)

    monkeypatch.setattr(JobService, "get_job_wait_state", get_job)
    task = asyncio.create_task(
        orchestrator.wait_for_answer(
            db,
            job_id="job-1",
            user_id="user-1",
            wait_seconds=1,
        )
    )
    await asyncio.sleep(0)
    await registry.set_job_event("job-1")

    result = await task

    assert result is answered
    assert db.rollbacks == 1
    assert registry.job_events == {}
    assert registry.job_event_waiters == {}


@pytest.mark.asyncio
async def test_wait_for_answer_cleans_event_when_initial_query_fails(monkeypatch):
    registry = RuntimeRegistry()
    orchestrator = JobOrchestrator(registry)

    async def fail_query(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(JobService, "get_job_wait_state", fail_query)
    with pytest.raises(RuntimeError, match="database unavailable"):
        await orchestrator.wait_for_answer(
            FakeDb(),
            job_id="job-1",
            user_id="user-1",
            wait_seconds=1,
        )

    assert registry.job_events == {}
    assert registry.job_event_waiters == {}


@pytest.mark.asyncio
async def test_kill_cannot_overtake_job_start_after_claim(monkeypatch):
    registry = RuntimeRegistry()
    await registry.register_launcher("launcher-1", object())
    orchestrator = JobOrchestrator(registry)
    job = SimpleNamespace(
        id="job-1",
        launcher_id="launcher-1",
        user_id="user-1",
        handler_type="ai.chat",
        slave_app_id="ai",
        offer={"type": "offer", "sdp": "v=0\r\n"},
        state="assigned",
    )
    claims = [(job, "launcher-1"), None]
    messages = []
    start_entered = asyncio.Event()
    allow_start = asyncio.Event()

    class Session:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *_args):
            return None

    async def claim(*_args, **_kwargs):
        return claims.pop(0)

    async def request_kill(*_args, **_kwargs):
        return job

    async def send(_launcher_id, message):
        messages.append(message["type"])
        if message["type"] == "job.start":
            start_entered.set()
            await allow_start.wait()

    monkeypatch.setattr("app.service.job_orchestrator.SessionLocal", Session)
    monkeypatch.setattr(JobService, "claim_next_compatible_job", claim)
    monkeypatch.setattr(JobService, "request_kill", request_kill)
    monkeypatch.setattr("app.service.job_orchestrator.send_to_launcher", send)

    dispatch = asyncio.create_task(orchestrator.dispatch_available_jobs())
    await asyncio.wait_for(start_entered.wait(), timeout=1)
    kill = asyncio.create_task(
        orchestrator.kill_job(
            object(),
            job_id="job-1",
            user_id="user-1",
            reason="test",
        )
    )
    await asyncio.sleep(0)
    assert messages == ["job.start"]

    allow_start.set()
    await asyncio.wait_for(asyncio.gather(dispatch, kill), timeout=1)
    assert messages == ["job.start", "job.cancel"]


@pytest.mark.asyncio
async def test_dispatch_sends_independent_launcher_starts_concurrently(monkeypatch):
    registry = RuntimeRegistry()
    await registry.register_launcher("launcher-1", object())
    await registry.register_launcher("launcher-2", object())
    orchestrator = JobOrchestrator(registry)
    jobs = [
        SimpleNamespace(
            id=f"job-{index}",
            launcher_id=f"launcher-{index}",
            user_id="user-1",
            handler_type="ai.chat",
            slave_app_id="ai",
            offer={"type": "offer", "sdp": "v=0\r\n"},
            state="assigned",
        )
        for index in (1, 2)
    ]
    claims = [(jobs[0], "launcher-1"), (jobs[1], "launcher-2"), None]
    slow_release = asyncio.Event()
    fast_sent = asyncio.Event()

    class Session:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *_args):
            return None

    async def claim(*_args, **_kwargs):
        return claims.pop(0)

    async def send(launcher_id, _message):
        if launcher_id == "launcher-1":
            await slow_release.wait()
        else:
            fast_sent.set()

    monkeypatch.setattr("app.service.job_orchestrator.SessionLocal", Session)
    monkeypatch.setattr(JobService, "claim_next_compatible_job", claim)
    monkeypatch.setattr("app.service.job_orchestrator.send_to_launcher", send)

    dispatch = asyncio.create_task(orchestrator.dispatch_available_jobs())
    await asyncio.wait_for(fast_sent.wait(), timeout=1)
    assert not dispatch.done()

    slow_release.set()
    assert await asyncio.wait_for(dispatch, timeout=1) == 2


@pytest.mark.asyncio
async def test_claim_failure_waits_for_already_claimed_delivery_without_cancelling_it(monkeypatch):
    registry = RuntimeRegistry()
    await registry.register_launcher("launcher-1", object())
    await registry.register_launcher("launcher-2", object())
    orchestrator = JobOrchestrator(registry)
    job = SimpleNamespace(
        id="job-1",
        launcher_id="launcher-1",
        user_id="user-1",
        handler_type="ai.chat",
        slave_app_id="ai",
        offer={"type": "offer", "sdp": "v=0\r\n"},
        state="assigned",
    )
    calls = 0
    send_started = asyncio.Event()
    send_release = asyncio.Event()

    class Session:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *_args):
            return None

    async def claim(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return job, "launcher-1"
        raise RuntimeError("database unavailable")

    async def send(_launcher_id, _message):
        send_started.set()
        await send_release.wait()

    monkeypatch.setattr("app.service.job_orchestrator.SessionLocal", Session)
    monkeypatch.setattr(JobService, "claim_next_compatible_job", claim)
    monkeypatch.setattr("app.service.job_orchestrator.send_to_launcher", send)

    dispatch = asyncio.create_task(orchestrator.dispatch_available_jobs())
    await asyncio.wait_for(send_started.wait(), timeout=1)
    assert not dispatch.done()

    send_release.set()
    with pytest.raises(RuntimeError, match="database unavailable"):
        await asyncio.wait_for(dispatch, timeout=1)


@pytest.mark.asyncio
async def test_periodic_access_key_revalidation_batches_and_disconnects_invalid_launchers(monkeypatch):
    class WebSocket:
        def __init__(self):
            self.close_code = None

        async def close(self, *, code):
            self.close_code = code

    class Db:
        def add(self, _item):
            return None

        async def rollback(self):
            return None

    class Session:
        async def __aenter__(self):
            return Db()

        async def __aexit__(self, *_args):
            return None

    registry = RuntimeRegistry()
    active_socket = WebSocket()
    inactive_socket = WebSocket()
    active = await registry.register_launcher("launcher-active", active_socket, access_key_id="key-active")
    inactive = await registry.register_launcher("launcher-inactive", inactive_socket, access_key_id="key-inactive")
    active.last_access_key_check_at -= 31
    inactive.last_access_key_check_at -= 31
    orchestrator = JobOrchestrator(registry)
    checks = []
    disconnected = []

    async def active_key_ids(_db, access_key_ids):
        checks.append(access_key_ids)
        return {"key-active"}

    async def disconnect_jobs(_db, *, launcher_ids, detail):
        disconnected.append((launcher_ids, detail))
        return []

    monkeypatch.setattr("app.service.job_orchestrator.SessionLocal", Session)
    monkeypatch.setattr("app.service.job_orchestrator.AccessKeyService.active_launcher_key_ids", active_key_ids)
    monkeypatch.setattr(JobService, "disconnect_launchers_and_fail_jobs", disconnect_jobs)

    assert await orchestrator.revalidate_launcher_access_keys() == 1
    assert checks == [{"key-active", "key-inactive"}]
    assert disconnected == [({"launcher-inactive"}, "launcher access key is no longer active")]
    assert await registry.get_launcher("launcher-active") is not None
    assert await registry.get_launcher("launcher-inactive") is None
    assert inactive_socket.close_code == 1008


@pytest.mark.asyncio
async def test_launcher_event_must_match_runtime_current_job():
    registry = RuntimeRegistry()
    await registry.register_launcher("launcher-1", object())
    await registry.mark_launcher_job("launcher-1", "job-owned")
    orchestrator = JobOrchestrator(registry)
    message = parse_launcher_message({"type": "job.running", "job_id": "job-other"})

    with pytest.raises(LauncherPolicyViolation, match="assigned job"):
        await orchestrator.handle_launcher_job_event(
            object(),
            launcher_id="launcher-1",
            user_id="user-1",
            message=message,
        )


@pytest.mark.asyncio
async def test_launcher_event_rejects_wrong_db_owner_or_state(monkeypatch):
    registry = RuntimeRegistry()
    await registry.register_launcher("launcher-1", object())
    await registry.mark_launcher_job("launcher-1", "job-1")
    orchestrator = JobOrchestrator(registry)

    async def reject_transition(*_args, **_kwargs):
        return None

    monkeypatch.setattr(JobService, "mark_launcher_running", reject_transition)
    message = parse_launcher_message({"type": "job.running", "job_id": "job-1"})

    with pytest.raises(LauncherPolicyViolation, match="ownership or state"):
        await orchestrator.handle_launcher_job_event(
            object(),
            launcher_id="launcher-1",
            user_id="user-1",
            message=message,
        )


@pytest.mark.asyncio
async def test_oversized_launcher_progress_is_policy_violation():
    registry = RuntimeRegistry()
    await registry.register_launcher("launcher-1", object())
    await registry.mark_launcher_job("launcher-1", "job-1")
    orchestrator = JobOrchestrator(registry)
    message = parse_launcher_message(
        {
            "type": "job.progress",
            "job_id": "job-1",
            "progress": "x" * JOB_PROGRESS_MAX_BYTES,
        }
    )

    with pytest.raises(LauncherPolicyViolation, match="exceeds"):
        await orchestrator.handle_launcher_job_event(
            object(),
            launcher_id="launcher-1",
            user_id="user-1",
            message=message,
        )
