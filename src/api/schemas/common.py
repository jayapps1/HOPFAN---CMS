from typing import Literal

from pydantic import BaseModel, ConfigDict


class ApiResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(ApiResponse):
    status: Literal["ok"] = "ok"
    service: Literal["hopfan-api"] = "hopfan-api"


class ReadinessResponse(ApiResponse):
    status: Literal["ready"] = "ready"
    database: Literal["available"] = "available"


class VersionResponse(ApiResponse):
    application: Literal["HOPFAN"] = "HOPFAN"
    api_version: Literal["v1"] = "v1"
    platform: Literal["online"] = "online"


class ErrorDetail(ApiResponse):
    code: str
    message: str


class ErrorResponse(ApiResponse):
    error: ErrorDetail
