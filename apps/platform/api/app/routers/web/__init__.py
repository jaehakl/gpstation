from fastapi import APIRouter

from routers.web import auth, jobs, users, worker_sessions

router = APIRouter(prefix="/web")
router.include_router(auth.router)
router.include_router(jobs.router)
router.include_router(users.router)
router.include_router(worker_sessions.router)
