from fastapi import APIRouter

from src.api.schemas.common import VersionResponse
from src.api.v1 import API_PREFIX

router = APIRouter(prefix=API_PREFIX, tags=["System"])


@router.get("/version", response_model=VersionResponse)
def version() -> VersionResponse:
    return VersionResponse()
