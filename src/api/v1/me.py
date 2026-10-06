from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user, get_db
from src.api.schemas.user import CurrentUserResponse
from src.api.v1 import API_PREFIX
from src.services.current_user_service import current_user_profile
from src.services.web_session_service import WebPrincipal

router = APIRouter(prefix=API_PREFIX, tags=["Current user"])


@router.get("/me", response_model=CurrentUserResponse)
def me(db: Annotated[Session, Depends(get_db, scope="function")],
       principal: Annotated[WebPrincipal, Depends(get_current_user)]) -> CurrentUserResponse:
    return CurrentUserResponse.model_validate(current_user_profile(db, principal))
