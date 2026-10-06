from datetime import date
from typing import Generic, TypeVar
from src.api.schemas.common import ApiResponse

T = TypeVar("T")
class Page(ApiResponse, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int
    pages: int

class MinistrySummary(ApiResponse):
    id: str
    name: str

class MemberRow(ApiResponse):
    id: str
    member_no: str
    full_name: str
    gender: str
    phone: str
    photo_url: str | None
    status: str
    ministries: list[MinistrySummary]

class LeadershipRow(ApiResponse):
    id: str
    ministry_id: str
    ministry_name: str
    member_id: str
    full_name: str
    member_no: str
    position_id: str
    position_name: str
    position_code: str
    is_leadership: bool
    is_current: bool
    start_date: date
    end_date: date | None

class Identity(ApiResponse):
    first_name: str
    middle_name: str
    last_name: str
    date_of_birth: str
    marital_status: str
class Contact(ApiResponse):
    phone: str
    alternate_phone: str
    email: str
    address: str
class Membership(ApiResponse):
    date_joined: str
    baptized: bool
    baptism_date: str
class HouseholdSummary(ApiResponse):
    id: str
    household_name: str
    household_code: str
    status: str
    relationship_label: str
class TeachingSummary(ApiResponse):
    class_name: str
    role_label: str
class SchoolSummary(ApiResponse):
    student: bool
    class_id: str | None = None
    class_name: str = ""
    status: str | None = None
    teachers: list[TeachingSummary]
class MemberDetail(MemberRow):
    identity: Identity
    contact: Contact
    membership: Membership
    leadership: list[LeadershipRow] | None = None
    household: HouseholdSummary | None = None
    sunday_school: SchoolSummary | None = None
class MinistryRow(ApiResponse):
    id: str
    code: str
    name: str
    description: str
    category: str
    status: str
    member_count: int | None
    active_member_count: int | None
class LeadershipCounts(ApiResponse):
    positions: int
    current: int
    members: int
    vacant: int
class MinistryDetail(MinistryRow):
    leadership: LeadershipCounts | None
    can_view_members: bool
    can_view_leadership: bool
class Metric(ApiResponse):
    key: str
    label: str
    value: int | float | None
    detail: str = ""
class DashboardResponse(ApiResponse):
    scope: str
    metrics: list[Metric]
    recent_members: list[MemberRow]
    unavailable: list[str]
