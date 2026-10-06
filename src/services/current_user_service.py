"""Explicit safe current-user projection; shared RBAC supplies all grants."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import Ministry, SundaySchoolClass
from src.services.web_session_service import WebPrincipal


def current_user_profile(db: Session, principal: WebPrincipal) -> dict:
    user, access = principal.user, principal.authorization
    scopes = db.scalars(select(Ministry).where(Ministry.id.in_(access.scope_ids),
                        Ministry.is_active.is_(True)).order_by(Ministry.name)).all()
    member = user.member
    school_scopes = []
    if access.has_any({"SUNDAY_SCHOOL_VIEW", "SUNDAY_SCHOOL_VIEW_ALL"}):
        from src.services.sunday_school_base import SundaySchoolBase
        school = SundaySchoolBase.access(db, user.id, auth=access)
        school_scopes = [dict(id=row.id, code=row.code, name=row.name) for row in db.scalars(
            select(SundaySchoolClass).where(SundaySchoolClass.id.in_(school.class_ids)).order_by(SundaySchoolClass.name))]
    dashboard = ("CHURCH_ADMIN" if access.has_any({"MEMBERS_VIEW_ALL", "MINISTRIES_VIEW_ALL", "ATTENDANCE_VIEW_ALL"})
                 else "SUNDAY_SCHOOL" if access.has_any({"SUNDAY_SCHOOL_VIEW", "SUNDAY_SCHOOL_VIEW_ALL"})
                 else "MINISTRY_OFFICER" if scopes else "STANDARD")
    return dict(
        id=user.id, username=user.username, email=user.email,
        member=dict(id=member.id, member_no=member.member_no, full_name=member.full_name, photo_url=None) if member else None,
        roles=[dict(code=role.code, name=role.name) for role in sorted(user.roles, key=lambda role: role.code) if role.is_active],
        permissions=sorted(access.permissions),
        ministry_scopes=[dict(id=ministry.id, code=ministry.code, name=ministry.name) for ministry in scopes],
        sunday_school_scopes=school_scopes, dashboard_profile=dashboard,
    )
