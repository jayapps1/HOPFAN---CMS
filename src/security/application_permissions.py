"""Application navigation and member grants, independent of role titles."""
from src.security.household_permissions import PERMISSIONS as HOUSEHOLD_PERMISSIONS
from src.security.sunday_school_permissions import PERMISSIONS as SCHOOL_PERMISSIONS
from src.security.content_permissions import PERMISSIONS as CONTENT_PERMISSIONS
from src.security.donation_permissions import PERMISSIONS as DONATION_PERMISSIONS
PERMISSIONS = {
    "MEMBERS_VIEW_ALL": "View the church member directory",
    "MEMBERS_VIEW_OWN_MINISTRY": "View members of assigned ministries",
    "MEMBERS_CREATE": "Register church members",
    "MEMBERS_EDIT": "Edit church member profiles",
    "MINISTRIES_VIEW_ALL": "View all ministries",
    "MINISTRIES_VIEW_OWN": "View assigned ministries",
    "MINISTRIES_CREATE": "Create church ministries",
    "MINISTRIES_EDIT": "Edit and activate church ministries",
    "MINISTRIES_DEACTIVATE": "Deactivate church ministries",
    "MINISTRIES_ARCHIVE": "Archive church ministries",
    "MINISTRIES_RESTORE": "Restore archived church ministries",
    "MINISTRIES_DELETE_UNUSED": "Permanently delete unused ministries",
    "MINISTRY_POSITION_VIEW": "View positions in permitted ministries",
    "MINISTRY_POSITION_CREATE": "Define ministry positions",
    "MINISTRY_POSITION_EDIT": "Edit ministry positions",
    "MINISTRY_POSITION_ARCHIVE": "Deactivate ministry positions",
    "MINISTRY_POSITION_DELETE_UNUSED": "Delete unused ministry positions",
    "MINISTRY_LEADERSHIP_VIEW": "View leadership in assigned ministries",
    "MINISTRY_LEADERSHIP_VIEW_ALL": "View all ministry leadership",
    "MINISTRY_LEADERSHIP_ASSIGN": "Appoint members to ministry positions",
    "MINISTRY_LEADERSHIP_EDIT": "Correct ministry appointments",
    "MINISTRY_LEADERSHIP_END": "End and replace ministry appointments",
    "SUNDAY_SCHOOL_VIEW": "View Sunday School workspace",
    "FINANCE_VIEW": "View finance workspace",
    "WELFARE_VIEW": "View welfare workspace",
    "SMS_VIEW_ALL": "View church SMS workspace",
    "SMS_VIEW_OWN": "View assigned ministry SMS workspace",
    "ADMINISTRATION_VIEW": "View administration workspace",
}
LEADER_PERMISSIONS = {"MEMBERS_VIEW_OWN_MINISTRY", "MINISTRIES_VIEW_OWN", "SMS_VIEW_OWN",
                      "MINISTRY_POSITION_VIEW", "MINISTRY_LEADERSHIP_VIEW"}
PERMISSIONS.update(HOUSEHOLD_PERMISSIONS)
PERMISSIONS.update(SCHOOL_PERMISSIONS)
PERMISSIONS.update(CONTENT_PERMISSIONS)
PERMISSIONS.update(DONATION_PERMISSIONS)


def navigation(capabilities):
    """Return only granted destinations; services still authorize every request."""
    permissions = set(capabilities.get("permissions", []))
    scoped = bool(capabilities.get("scope_ids"))
    items = [("Dashboard", "home")]
    if "MEMBERS_VIEW_ALL" in permissions or (scoped and "MEMBERS_VIEW_OWN_MINISTRY" in permissions) or permissions.intersection({'HOUSEHOLD_VIEW','HOUSEHOLD_VIEW_ALL'}):
        items.append(("Members", "users"))
    if capabilities.get("can_view"):
        items.append(("Attendance", "attendance"))
    if "MINISTRIES_VIEW_ALL" in permissions or (scoped and "MINISTRIES_VIEW_OWN" in permissions):
        items.append(("Ministries", "ministries"))
    for name, image, grant in (("Sunday School", "book", "SUNDAY_SCHOOL_VIEW"),
                               ("Finance", "finance", "FINANCE_VIEW"), ("Welfare", "heart", "WELFARE_VIEW")):
        if grant in permissions or (name=='Sunday School' and 'SUNDAY_SCHOOL_VIEW_ALL' in permissions):
            items.append((name, image))
    if "SMS_VIEW_ALL" in permissions or (scoped and "SMS_VIEW_OWN" in permissions):
        items.append(("SMS", "message"))
    if capabilities.get("can_view") and capabilities.get("can_report", "ATTENDANCE_EXPORT" in permissions):
        items.append(("Reports", "chart"))
    if "ADMINISTRATION_VIEW" in permissions or permissions.intersection({"USER_VIEW", "ROLE_VIEW", "PERMISSION_VIEW", "SECURITY_AUDIT_VIEW"}):
        items.append(("Administration", "settings"))
    return items
