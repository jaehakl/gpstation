from fastapi import APIRouter, Depends

from models import UserData
from user_auth.utils.access_key_auth import require_access_key_roles

router = APIRouter(prefix="/users", tags=["app-v1-users"])


@router.get("/me", response_model=UserData)
async def api_v1_get_me(
    current_user: UserData = Depends(require_access_key_roles(["admin", "user"])),
):
    return current_user
