"""Family information requires explicit grants independent of ministry access."""
PERMISSIONS = {
    'HOUSEHOLD_VIEW': 'View the household linked to your own member record',
    'HOUSEHOLD_VIEW_ALL': 'View all household and family records',
    'HOUSEHOLD_CREATE': 'Create households',
    'HOUSEHOLD_EDIT': 'Edit households, relationships and household heads',
    'HOUSEHOLD_ADD_MEMBER': 'Add existing members to households',
    'HOUSEHOLD_REMOVE_MEMBER': 'End household memberships',
    'HOUSEHOLD_ARCHIVE': 'Archive and restore households',
    'HOUSEHOLD_DELETE_UNUSED': 'Permanently delete households without membership history',
}

RELATIONSHIPS = {
    'HEAD': 'Head of household', 'SPOUSE': 'Spouse', 'SON': 'Son', 'DAUGHTER': 'Daughter',
    'CHILD': 'Child', 'FATHER': 'Father', 'MOTHER': 'Mother', 'BROTHER': 'Brother',
    'SISTER': 'Sister', 'DEPENDANT': 'Dependant', 'GUARDIAN': 'Guardian',
    'RELATIVE': 'Relative', 'OTHER': 'Other',
}
MINOR_AGE = 18
