from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.api.schemas.common import ErrorResponse, HealthResponse, ReadinessResponse
from src.api.v1 import API_PREFIX
from src.services.api_readiness_service import check_database_readiness

router = APIRouter(prefix=API_PREFIX, tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Process liveness; deliberately independent of database availability."""
    return HealthResponse()


@router.get("/ready", response_model=ReadinessResponse, responses={503: {"model": ErrorResponse}})
def ready(db: Annotated[Session, Depends(get_db, scope="function")]) -> ReadinessResponse:
    """Read-only PostgreSQL readiness using the shared session factory."""
    check_database_readiness(db)
    return ReadinessResponse()
