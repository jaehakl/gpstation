from fastapi import APIRouter

from app.routers.v1 import sessions, launchers

router = APIRouter(prefix="/v1")
router.include_router(launchers.router)
router.include_router(sessions.router)
