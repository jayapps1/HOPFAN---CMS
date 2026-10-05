"""Ministry profile with membership totals and recorded configuration history."""
import customtkinter as ctk
from src.ui.components.modern import ActionButton, AppCard, FixedFooterDialog, StatusBadge, label
from src.ui.components.async_loader import AsyncLoader
from src.ui.components.date_picker import display_date


class MinistryProfileDialog(FixedFooterDialog):
    def __init__(self,master,service,ministry_id,leadership_service=None):
        super().__init__(master,'Ministry profile','Configuration, participation and lifecycle history.',width=790,height=720)
        self.ministry=None
        self.service,self.ministry_id=service,ministry_id
        self.active_tab='overview'
        self.leadership_view=None
        self.leadership_service=leadership_service
        if self.leadership_service is None and getattr(service,'user_id',None) is not None:
            from src.services.ministry_leadership_service import MinistryLeadershipService
            self.leadership_service=MinistryLeadershipService(service.user_id,service.session_factory)
        self.tabs=ctk.CTkFrame(self.header,fg_color='transparent')
        self.tabs.pack(fill='x',padx=18,pady=(0,12))
        self.overview_button=ActionButton(self.tabs,'Overview',self.overview,width=105)
        self.overview_button.pack(side='left')
        self.leadership_button=ActionButton(self.tabs,'Leadership',self.leadership,width=115)
        self.cancel_button.configure(text='Close')
        self.loader=AsyncLoader(self)
        self.refresh()

    def refresh(self):
        def load():
            ministry,history=self.service.get_ministry(self.ministry_id),self.service.audit_history(self.ministry_id)
            caps,stats={},None
            if self.leadership_service:
                caps=self.leadership_service.capabilities(self.ministry_id)
                if caps.get('view'): stats=self.leadership_service.leadership_stats(self.ministry_id)
            return ministry,history,caps,stats
        self.loader.submit('profile',load,self.render,lambda error:self.error_var.set(str(error)))

    def overview(self):
        self.active_tab='overview'
        if self.leadership_view:
            self.leadership_view.grid_remove()
            self.leadership_view.hide_actions()
            if self.leadership_view.profile_title: self.leadership_view.profile_title.configure(text='Ministry profile')
            if self.leadership_view.profile_subtitle:
                self.leadership_view.profile_subtitle.pack(anchor='w',padx=18,pady=(2,14),before=self.tabs)
        self.content.grid()
        self.refresh()

    def leadership(self):
        if not self.ministry or not self.leadership_service: return
        self.active_tab='leadership'
        self.content.grid_remove()
        if not self.leadership_view:
            from src.ui.ministries.leadership_view import MinistryLeadershipView
            self.leadership_view=MinistryLeadershipView(self,self.leadership_service,self.ministry)
        else:
            self.leadership_view.refresh()
            if self.leadership_view.profile_title: self.leadership_view.profile_title.configure(text=self.ministry['name']+' leadership')
            if self.leadership_view.profile_subtitle: self.leadership_view.profile_subtitle.pack_forget()
        self.leadership_view.grid(row=1,column=0,sticky='nsew',padx=18)
        return self.leadership_view

    def render(self,result):
        ministry,history,caps,leadership_stats=result
        self.ministry=ministry
        for child in self.content.winfo_children(): child.destroy()
        self.leadership_button.pack_forget()
        if caps.get('view'): self.leadership_button.pack(side='left',padx=8,after=self.overview_button)
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
        if leadership_stats is not None:
            summary=AppCard(self.content)
            summary.pack(fill='x',padx=16,pady=8)
            label(summary,'Leadership',16,True).pack(anchor='w',padx=14,pady=(12,4))
            text=f"{leadership_stats['current']} current appointments · {leadership_stats['vacant']} vacant positions"
            label(summary,text,12,muted=True).pack(anchor='w',padx=14)
            ActionButton(summary,'View leadership',self.leadership,width=145).pack(anchor='w',padx=14,pady=12)
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
