from __future__ import annotations

from fastapi import APIRouter

from app.routers.v1 import jobs, launchers

router = APIRouter(prefix="/v1")
router.include_router(launchers.router)
router.include_router(jobs.router)
