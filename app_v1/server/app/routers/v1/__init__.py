from fastapi import APIRouter

from app.routers.v1 import sessions, workers

router = APIRouter(prefix="/v1")
router.include_router(workers.router)
router.include_router(sessions.router)
