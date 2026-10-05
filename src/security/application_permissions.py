"""Application navigation and member grants, independent of role titles."""
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
    "SUNDAY_SCHOOL_VIEW": "View Sunday School workspace",
    "FINANCE_VIEW": "View finance workspace",
    "WELFARE_VIEW": "View welfare workspace",
    "SMS_VIEW_ALL": "View church SMS workspace",
    "SMS_VIEW_OWN": "View assigned ministry SMS workspace",
    "ADMINISTRATION_VIEW": "View administration workspace",
}
LEADER_PERMISSIONS = {"MEMBERS_VIEW_OWN_MINISTRY", "MINISTRIES_VIEW_OWN", "SMS_VIEW_OWN"}


def navigation(capabilities):
    """Return only granted destinations; services still authorize every request."""
    permissions = set(capabilities.get("permissions", []))
    scoped = bool(capabilities.get("scope_ids"))
    items = [("Dashboard", "home")]
    if "MEMBERS_VIEW_ALL" in permissions or (scoped and "MEMBERS_VIEW_OWN_MINISTRY" in permissions):
        items.append(("Members", "users"))
    if capabilities.get("can_view"):
        items.append(("Attendance", "attendance"))
    if "MINISTRIES_VIEW_ALL" in permissions or (scoped and "MINISTRIES_VIEW_OWN" in permissions):
        items.append(("Ministries", "ministries"))
    for name, image, grant in (("Sunday School", "book", "SUNDAY_SCHOOL_VIEW"),
                               ("Finance", "finance", "FINANCE_VIEW"), ("Welfare", "heart", "WELFARE_VIEW")):
        if grant in permissions:
            items.append((name, image))
    if "SMS_VIEW_ALL" in permissions or (scoped and "SMS_VIEW_OWN" in permissions):
        items.append(("SMS", "message"))
    if capabilities.get("can_view") and capabilities.get("can_report", "ATTENDANCE_EXPORT" in permissions):
        items.append(("Reports", "chart"))
    if "ADMINISTRATION_VIEW" in permissions:
        items.append(("Administration", "settings"))
    return items
