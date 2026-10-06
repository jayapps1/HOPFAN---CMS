from typing import Literal
from uuid import UUID

from src.api.schemas.common import ApiResponse


class MemberSummary(ApiResponse):
    id: UUID
    member_no: str
    full_name: str
    photo_url: None = None


class RoleSummary(ApiResponse):
    code: str
    name: str


class ScopeSummary(ApiResponse):
    id: UUID
    code: str
    name: str


class CurrentUserResponse(ApiResponse):
    id: UUID
    username: str
    email: str | None
    member: MemberSummary | None
    roles: list[RoleSummary]
    permissions: list[str]
    ministry_scopes: list[ScopeSummary]
    sunday_school_scopes: list[ScopeSummary]
    dashboard_profile: Literal["CHURCH_ADMIN", "SUNDAY_SCHOOL", "MINISTRY_OFFICER", "STANDARD"]
