from __future__ import annotations

from fastapi import APIRouter

from app.routers.web import auth, dashboard, launchers, slave_sessions, users

router = APIRouter(prefix="/web")
router.include_router(auth.router)
router.include_router(dashboard.router)
router.include_router(users.router)
router.include_router(launchers.router)
router.include_router(slave_sessions.router)
