"""Ministry profile with membership totals and recorded configuration history."""
from src.ui.components.modern import AppCard, FixedFooterDialog, StatusBadge, label
from src.ui.components.async_loader import AsyncLoader
from src.ui.components.date_picker import display_date


class MinistryProfileDialog(FixedFooterDialog):
    def __init__(self,master,service,ministry_id):
        super().__init__(master,'Ministry profile','Configuration, participation and lifecycle history.',width=790,height=720)
        self.ministry=None
        self.cancel_button.configure(text='Close')
        self.loader=AsyncLoader(self)
        self.loader.submit('profile',lambda:(service.get_ministry(ministry_id),service.audit_history(ministry_id)),
            self.render,lambda error:self.error_var.set(str(error)))

    def render(self,result):
        ministry,history=result
        self.ministry=ministry
        identity=AppCard(self.content)
        identity.pack(fill='x',padx=16,pady=12)
        label(identity,ministry['name'],22,True,anchor='w',wraplength=620).pack(fill='x',padx=16,pady=(16,4))
        label(identity,ministry['code']+' · '+ministry['category'].title(),12,muted=True,anchor='w').pack(fill='x',padx=16,pady=(0,8))
        StatusBadge(identity,ministry['status']).pack(anchor='w',padx=16,pady=(0,16))
        stats=AppCard(self.content)
        stats.pack(fill='x',padx=16,pady=8)
        label(stats,f"{ministry['member_count']} members  ·  {ministry['active_member_count']} active members",18,True,
            anchor='w',wraplength=620).pack(fill='x',padx=16,pady=16)
        label(self.content,'Counts use active ministry participation. Active members also have an Active member profile.',11,
            muted=True,wraplength=620,justify='left',anchor='w').pack(fill='x',padx=16,pady=(0,8))
        for title,value in (('Description',ministry['description'] or 'No description added.'),
            ('Created',display_date(ministry['created_at'])),('Updated',display_date(ministry['updated_at'])),
            ('Archived',display_date(ministry['archived_at']) if ministry['archived_at'] else 'Not archived')):
            card=AppCard(self.content)
            card.pack(fill='x',padx=16,pady=4)
            label(card,title,12,True).pack(anchor='w',padx=14,pady=(10,2))
            label(card,value,13,anchor='w',justify='left',wraplength=620).pack(fill='x',padx=14,pady=(0,10))
        if ministry.get('in_use'):
            label(self.content,'Linked church records are retained. Archive this ministry when it is no longer in use.',12,
                muted=True,anchor='w',justify='left',wraplength=620).pack(fill='x',padx=16,pady=12)
        label(self.content,'Configuration history',16,True).pack(anchor='w',padx=16,pady=(16,6))
        if not history:
            label(self.content,'No configuration changes recorded yet.',12,muted=True).pack(anchor='w',padx=16,pady=12)
        for change in history:
            card=AppCard(self.content)
            card.pack(fill='x',padx=16,pady=4)
            label(card,change['action'].replace('_',' ').title(),13,True).pack(anchor='w',padx=14,pady=(10,2))
            when=change['occurred_at'].astimezone().strftime('%d/%m/%Y %H:%M')
            label(card,change['actor']+' · '+when,11,muted=True).pack(anchor='w',padx=14,pady=(0,10))
