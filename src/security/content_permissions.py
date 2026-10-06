"""Explicit content, publication and intake capabilities."""
PERMISSIONS = {
    **{f'{kind}_{action}':label for kind,title in [('EVENT','events'),('ANNOUNCEMENT','announcements')]
       for action,label in [('VIEW_ALL',f'View all {title}'),('VIEW_OWN_MINISTRY',f'View assigned ministry {title}'),
        ('CREATE_GLOBAL',f'Create church-wide {title}'),('CREATE_OWN_MINISTRY',f'Create assigned ministry {title}'),
        ('EDIT_GLOBAL',f'Edit church-wide {title}'),('EDIT_OWN_MINISTRY',f'Edit assigned ministry {title}'),
        ('SUBMIT',f'Submit {title} for approval'),('APPROVE',f'Approve {title}'),('PUBLISH',f'Publish {title}'),
        ('CANCEL',f'Cancel or archive {title}')]},
    'WEBSITE_PAGE_VIEW':'View website CMS and private previews',
    'WEBSITE_PAGE_CREATE':'Create website pages and public editorial profiles',
    'WEBSITE_PAGE_EDIT':'Edit website pages, sermons and gallery content',
    'WEBSITE_PAGE_PUBLISH':'Publish, unpublish and archive website content',
    'WEBSITE_SETTINGS_MANAGE':'Manage website contacts, service times and configuration',
    'WEBSITE_MEDIA_MANAGE':'Upload and manage website media',
    'WEBSITE_MEDIA_PUBLISH':'Approve website media for public publication',
    'VISITOR_VIEW_ALL':'View private visitor and contact inquiries',
    'VISITOR_VIEW_OWN':'View inquiries assigned to your account',
    'VISITOR_EDIT':'Update permitted inquiries and follow-up notes',
    'VISITOR_ASSIGN':'Assign inquiry follow-up',
    'VISITOR_CONVERT':'Link or convert a reviewed visitor to a Member',
    'PRAYER_REQUEST_VIEW':'View private pastoral prayer requests',
    'PRAYER_REQUEST_EDIT':'Update private prayer request follow-up',
}
SENSITIVE={'PRAYER_REQUEST_VIEW','PRAYER_REQUEST_EDIT'}
OWN_EDITOR={f'{kind}_{action}_OWN_MINISTRY' for kind in ('EVENT','ANNOUNCEMENT') for action in ('VIEW','CREATE','EDIT')}|{'EVENT_SUBMIT','ANNOUNCEMENT_SUBMIT'}
