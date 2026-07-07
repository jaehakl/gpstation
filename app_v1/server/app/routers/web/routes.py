from __future__ import annotations

from fastapi import APIRouter

from app.routers.web import auth, crud_routes, slave_sessions, users

router = APIRouter(prefix="/web")
router.include_router(auth.router)
router.include_router(crud_routes.router)
router.include_router(users.router)
router.include_router(slave_sessions.router)
