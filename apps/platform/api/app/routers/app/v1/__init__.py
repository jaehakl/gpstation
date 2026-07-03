from fastapi import APIRouter

from routers.app.v1 import users, workers

router = APIRouter(prefix="/app/v1")
router.include_router(users.router)
router.include_router(workers.router)
