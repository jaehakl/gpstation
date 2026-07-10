from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy.dialects import postgresql

from app.user_auth.db import User  # noqa: F401
from app.db import Job
from app.service.job_service import (
    JOB_OFFER_MAX_BYTES,
    JOB_PROGRESS_MAX_BYTES,
    JobService,
)


class FakeRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows

    def scalars(self):
        return self

    def first(self):
        return self.rows[0] if self.rows else None


class FakeDb:
    def __init__(self, *, scalar_results=None, execute_results=None):
        self.scalar_results = list(scalar_results or [])
        self.execute_results = list(execute_results or [])
        self.added = []
        self.scalar_statements = []
        self.execute_statements = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = str(uuid.uuid4())
        self.added.append(obj)

    async def scalar(self, stmt):
        self.scalar_statements.append(stmt)
        return self.scalar_results.pop(0) if self.scalar_results else None

    async def execute(self, stmt):
        self.execute_statements.append(stmt)
        rows = self.execute_results.pop(0) if self.execute_results else []
        return FakeRows(rows)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, _obj):
        return None


def make_job(state="queued", launcher_id=None):
    now = datetime.now(timezone.utc)
    return Job(
        id="job-1",
        user_id="user-1",
        launcher_id=launcher_id,
        handler_type="ai.llm",
        slave_app_id="ai",
        offer={"type": "offer", "sdp": "v=0\r\n"},
        result={"ok": True},
        state=state,
        progress=[],
        attempt_count=0,
        created_at=now,
        updated_at=now,
    )


def sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


@pytest.mark.asyncio
async def test_create_job_persists_queued_offer_without_input_body():
    db = FakeDb()

    job = await JobService.create_job(
        db,
        user_id="user-1",
        handler_type="ai.llm",
        slave_app_id="ai",
        offer={"type": "offer", "sdp": "v=0\r\n"},
    )

    assert job.state == "queued"
    assert job.input is None
    assert job.offer == {"type": "offer", "sdp": "v=0\r\n"}
    assert db.added == [job]
    assert db.commits == 1


@pytest.mark.asyncio
async def test_create_job_rejects_non_offer_and_oversized_offer():
    db = FakeDb()

    with pytest.raises(ValueError, match="SDP offer"):
        await JobService.create_job(
            db,
            user_id="user-1",
            handler_type="ai.llm",
            slave_app_id="ai",
            offer={"type": "answer", "sdp": "v=0\r\n"},
        )

    with pytest.raises(ValueError, match="request exceeds"):
        await JobService.create_job(
            db,
            user_id="user-1",
            handler_type="ai.llm",
            slave_app_id="ai",
            offer={"type": "offer", "sdp": "x" * JOB_OFFER_MAX_BYTES},
        )


@pytest.mark.asyncio
async def test_claim_job_skips_incompatible_queue_and_locks_job_and_launcher():
    launcher = SimpleNamespace(
        id="launcher-1",
        user_id="user-1",
        slave_app_ids=["ai"],
        status="ready",
        updated_at=None,
    )
    job = make_job()
    db = FakeDb(execute_results=[[(job, launcher)]])

    assignment = await JobService.claim_next_compatible_job(
        db,
        idle_launcher_ids={"launcher-1"},
    )

    assert assignment == (job, "launcher-1")
    assert job.state == "assigned"
    assert job.launcher_id == "launcher-1"
    assert job.attempt_count == 1
    assert launcher.status == "busy"
    assignment_select = sql(db.execute_statements[0])
    assert "launchers.user_id = jobs.user_id" in assignment_select
    assert "launchers.slave_app_ids ? jobs.slave_app_id" in assignment_select
    assert "FOR UPDATE OF jobs, launchers SKIP LOCKED" in assignment_select


@pytest.mark.asyncio
async def test_job_summary_query_does_not_load_sdp_or_progress_payloads():
    now = datetime.now(timezone.utc)
    row = SimpleNamespace(
        id="job-1",
        user_id="user-1",
        handler_type="ai.llm",
        slave_app_id="ai",
        state="running",
        launcher_id="launcher-1",
        assigned_at=now,
        answer_ready_at=now,
        started_at=now,
        finished_at=None,
        cancel_requested_at=None,
        last_error=None,
        attempt_count=1,
        created_at=now,
        updated_at=now,
    )
    db = FakeDb(execute_results=[[row]])

    summaries = await JobService.list_job_summaries(
        db,
        user_id="user-1",
        active_only=True,
        limit=100,
    )

    assert summaries[0].id == "job-1"
    statement = sql(db.execute_statements[0])
    assert "jobs.offer" not in statement
    assert "jobs.answer, " not in statement
    assert "jobs.progress" not in statement


@pytest.mark.asyncio
async def test_request_kill_marks_queued_job_killed_but_active_job_waits_for_ack():
    queued = make_job(state="queued")
    active = make_job(state="running", launcher_id="launcher-1")
    db = FakeDb(scalar_results=[queued, active])

    await JobService.request_kill(db, job_id=queued.id, user_id=queued.user_id)
    await JobService.request_kill(db, job_id=active.id, user_id=active.user_id)

    assert queued.state == "killed"
    assert queued.cancel_requested_at is not None
    assert queued.finished_at is not None
    assert active.state == "running"
    assert active.cancel_requested_at is not None


@pytest.mark.asyncio
async def test_launcher_result_update_contains_full_ownership_and_state_predicate():
    job = make_job(state="succeeded", launcher_id="launcher-1")
    db = FakeDb(scalar_results=[job])

    result = await JobService.mark_launcher_result(
        db,
        job_id=job.id,
        launcher_id="launcher-1",
        user_id="user-1",
    )

    assert result is job
    statement = sql(db.scalar_statements[0])
    assert "jobs.id" in statement
    assert "jobs.launcher_id" in statement
    assert "jobs.user_id" in statement
    assert "jobs.state IN" in statement
    assert "RETURNING jobs" in statement
    assert "UPDATE launchers" in sql(db.execute_statements[0])


@pytest.mark.asyncio
async def test_launcher_progress_has_event_and_cumulative_limits():
    with pytest.raises(ValueError, match="exceeds"):
        await JobService.append_launcher_progress(
            FakeDb(),
            job_id="job-1",
            launcher_id="launcher-1",
            user_id="user-1",
            progress="x" * JOB_PROGRESS_MAX_BYTES,
        )

    db = FakeDb(scalar_results=[None])
    await JobService.append_launcher_progress(
        db,
        job_id="job-1",
        launcher_id="launcher-1",
        user_id="user-1",
        progress={"token": "hello"},
    )
    statement = sql(db.scalar_statements[0])
    assert "jsonb_array_length(jobs.progress)" in statement
    assert "jobs.progress || CAST" in statement


@pytest.mark.asyncio
async def test_restart_recovery_atomically_disconnects_launchers_and_fails_jobs():
    job = make_job(state="failed", launcher_id="launcher-1")
    db = FakeDb(execute_results=[[], [job]])

    recovered = await JobService.recover_after_server_restart(db)

    assert recovered == [job]
    assert db.commits == 1
    launcher_update = sql(db.execute_statements[0])
    job_update = sql(db.execute_statements[1])
    assert "UPDATE launchers" in launcher_update
    assert "launchers.disconnected_at IS NULL" in launcher_update
    assert "UPDATE jobs" in job_update
    assert "jobs.launcher_id IS NOT NULL" in job_update
    assert "jobs.state IN" in job_update
    assert "last_error" in job_update
