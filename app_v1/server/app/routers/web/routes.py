from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.routers.web import auth, crud_routes, jobs, launchers, users

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


async def require_web_csrf(request: Request) -> None:
    if request.method.upper() in UNSAFE_METHODS:
        auth.validate_csrf_request(request)


router = APIRouter(prefix="/web", dependencies=[Depends(require_web_csrf)])
router.include_router(auth.router)
router.include_router(crud_routes.router)
router.include_router(launchers.router)
router.include_router(jobs.router)
router.include_router(users.router)
