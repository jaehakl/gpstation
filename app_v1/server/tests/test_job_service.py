from datetime import datetime, timezone
import uuid

import pytest

from app.user_auth.db import User  # noqa: F401
from app.db import Job, Launcher
from app.service.job_service import JobService


class FakeScalarRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeExecuteResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return FakeScalarRows(self.rows)


class FakeDb:
    def __init__(self, *, jobs=None, launchers=None):
        self.jobs = {job.id: job for job in jobs or []}
        self.launchers = {launcher.id: launcher for launcher in launchers or []}
        self.added = []
        self.commits = 0

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = str(uuid.uuid4())
        self.added.append(obj)
        if isinstance(obj, Job):
            self.jobs[obj.id] = obj

    async def get(self, model, object_id):
        if model is Job:
            return self.jobs.get(object_id)
        if model is Launcher:
            return self.launchers.get(object_id)
        return None

    async def execute(self, _stmt):
        return FakeExecuteResult(list(self.launchers.values()))

    async def commit(self):
        self.commits += 1

    async def refresh(self, _obj):
        return None


def make_launcher(launcher_id="launcher-1", user_id="user-1", slave_app_ids=None, status="ready"):
    return Launcher(
        id=launcher_id,
        user_id=user_id,
        launcher_name="desktop",
        ip_address="127.0.0.1",
        status=status,
        slave_app_ids=slave_app_ids or ["echo"],
        active_session_ids=[],
        connected_at=datetime.now(timezone.utc),
        last_heartbeat_at=datetime.now(timezone.utc),
    )


def make_job(state="queued", launcher_id=None):
    return Job(
        id="job-1",
        user_id="user-1",
        launcher_id=launcher_id,
        handler_type="echo.request",
        slave_app_id="echo",
        offer={"type": "offer", "sdp": "v=0\r\n"},
        result={"ok": True},
        state=state,
        progress=[],
        attempt_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_create_job_persists_queued_offer_without_input_body():
    db = FakeDb()

    job = await JobService.create_job(
        db,
        user_id="user-1",
        handler_type="echo.request",
        slave_app_id="echo",
        offer={"type": "offer", "sdp": "v=0\r\n"},
    )

    assert job.state == "queued"
    assert job.input is None
    assert job.offer == {"type": "offer", "sdp": "v=0\r\n"}
    assert db.added == [job]
    assert db.commits == 1


@pytest.mark.asyncio
async def test_create_job_rejects_non_offer_signal():
    db = FakeDb()

    with pytest.raises(ValueError, match="SDP offer"):
        await JobService.create_job(
            db,
            user_id="user-1",
            handler_type="echo.request",
            slave_app_id="echo",
            offer={"type": "answer", "sdp": "v=0\r\n"},
        )


@pytest.mark.asyncio
async def test_assign_job_marks_launcher_busy_and_counts_attempt():
    launcher = make_launcher()
    job = make_job()
    db = FakeDb(jobs=[job], launchers=[launcher])

    await JobService.assign_job(db, job=job, launcher=launcher)

    assert job.state == "assigned"
    assert job.launcher_id == launcher.id
    assert job.assigned_at is not None
    assert job.attempt_count == 1
    assert launcher.status == "busy"
    assert db.commits == 1


@pytest.mark.asyncio
async def test_request_kill_marks_queued_job_killed():
    job = make_job(state="queued")
    db = FakeDb(jobs=[job])

    await JobService.request_kill(db, job=job)

    assert job.state == "killed"
    assert job.cancel_requested_at is not None
    assert job.finished_at is not None


@pytest.mark.asyncio
async def test_result_clears_launcher_to_ready():
    launcher = make_launcher(status="busy")
    job = make_job(state="running", launcher_id=launcher.id)
    db = FakeDb(jobs=[job], launchers=[launcher])

    await JobService.mark_result(db, job_id=job.id)

    assert job.state == "succeeded"
    assert job.result is None
    assert job.finished_at is not None
    assert launcher.status == "ready"
