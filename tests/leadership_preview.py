"""In-memory fixtures for desktop interaction and layout checks only."""
from datetime import date, datetime, timedelta, timezone
import uuid
from src.services.ministry_leadership_service import MinistryLeadershipService, LeadershipServiceError, MembershipRequiredError, PositionConflictError


class PreviewLeadershipService:
    _position_values=staticmethod(MinistryLeadershipService._position_values)
    _dates=classmethod(MinistryLeadershipService._dates.__func__)
    _date=staticmethod(MinistryLeadershipService._date)

    def __init__(self,ministry,management=True,current=True):
        self.ministry,self.management=ministry,management
        self.positions,self.appointments,self.changes=[],[],[]
        self.members=[dict(id=str(uuid.uuid4()),full_name=name,member_no=f'PREVIEW-{index+1:04d}',phone='054 000 0000',photo_path='',in_ministry=index!=2)
            for index,name in enumerate(['Daniel Owusu','Kwame Mensah','Ama Mensah']+[f'Synthetic Member {i}' for i in range(27)])]
        self.create_position(ministry['id'],dict(name='Leader',code='LEADER',sort_order=1))
        self.create_position(ministry['id'],dict(name='Secretary',code='SECRETARY',sort_order=2))
        if current: self.assign_member(ministry['id'],self.members[0]['id'],self.positions[0]['id'],date.today()-timedelta(days=90))

    def capabilities(self,_mid):
        return dict(view=True,positions_view=True,member_search=True,**{key:self.management for key in
            ('position_create','position_edit','position_archive','position_delete','assign','edit','end','add_membership')})

    def create_position(self,mid,data):
        row=dict(self._position_values(data),id=str(uuid.uuid4()),ministry_id=mid,updated_at=datetime.now(timezone.utc),created_at=datetime.now(timezone.utc),in_use=False,current_holders=0)
        row['description']=row['description'] or ''
        self.positions.append(row)
        return dict(row)

    def list_positions(self,_mid,active_only=False):
        rows=[]
        for row in self.positions:
            if active_only and not row['is_active']: continue
            holders=sum(a['position_id']==row['id'] and a['is_current'] for a in self.appointments)
            used=any(a['position_id']==row['id'] for a in self.appointments)
            rows.append(dict(row,current_holders=holders,in_use=used))
        return sorted(rows,key=lambda row:(row['sort_order'],row['name']))

    def update_position(self,pid,data,*_args):
        row=next(p for p in self.positions if p['id']==pid)
        row.update(self._position_values(data),updated_at=datetime.now(timezone.utc))
        return dict(row)

    def deactivate_position(self,pid,*_args):
        row=next(p for p in self.positions if p['id']==pid)
        if any(a['position_id']==pid and a['is_current'] for a in self.appointments): raise LeadershipServiceError('End current assignments first.')
        row.update(is_active=False,updated_at=datetime.now(timezone.utc))

    def delete_unused_position(self,pid,**_kwargs):
        if any(a['position_id']==pid for a in self.appointments): raise LeadershipServiceError('Assignment history exists.')
        self.positions=[p for p in self.positions if p['id']!=pid]

    def candidate_members(self,_mid,search='',offset=0,limit=20):
        rows=[m for m in self.members if search.casefold() in (m['full_name']+' '+m['member_no']+' '+m['phone']).casefold()]
        return dict(total=len(rows),rows=rows[offset:offset+limit])

    def assign_member(self,ministry_id,member_id,position_id,start_date,end_date=None,notes='',add_membership=False,replace_assignment_id=None,**_kwargs):
        member=next(m for m in self.members if m['id']==str(member_id))
        position=next(p for p in self.positions if p['id']==position_id)
        if not member['in_ministry'] and not add_membership: raise MembershipRequiredError(member['full_name']+' is not currently a member of '+self.ministry['name']+'.')
        holders=[a for a in self.appointments if a['position_id']==position_id and a['is_current']]
        if holders and position['max_current_holders']==1 and not replace_assignment_id and not end_date:
            raise PositionConflictError(position,[dict(id=a['id'],full_name=a['full_name'],updated_at=a['updated_at']) for a in holders])
        if replace_assignment_id: self.end_assignment(replace_assignment_id,start_date,'Replacement')
        if add_membership: member['in_ministry']=True
        row=dict(id=str(uuid.uuid4()),ministry_id=ministry_id,ministry_name=self.ministry['name'],member_id=member_id,full_name=member['full_name'],member_no=member['member_no'],phone=member['phone'],photo_path='',
            position_id=position_id,position_name=position['name'],position_code=position['code'],is_leadership=True,position_active=True,is_current=end_date is None,start_date=start_date,end_date=end_date,notes=notes,
            updated_at=datetime.now(timezone.utc),created_at=datetime.now(timezone.utc))
        self.appointments.append(row)
        self.changes.append('assigned')
        return dict(row)

    def get_assignment(self,aid): return dict(next(a for a in self.appointments if a['id']==aid))

    def update_assignment(self,aid,data,*_args):
        row=next(a for a in self.appointments if a['id']==aid)
        row.update(data,updated_at=datetime.now(timezone.utc))
        self.changes.append('edited')
        return dict(row)

    def end_assignment(self,aid,end_date,notes='',*_args):
        row=next(a for a in self.appointments if a['id']==aid)
        row.update(is_current=False,end_date=end_date,notes=notes,updated_at=datetime.now(timezone.utc))
        self.changes.append('ended')
        return dict(row)

    def list_leadership(self,mid,status='CURRENT',search='',offset=0,limit=20):
        if status=='VACANT':
            rows=[p for p in self.list_positions(mid,True) if p['current_holders']<(p['max_current_holders'] or 1)]
        else: rows=[dict(a) for a in self.appointments if a['is_current']==(status=='CURRENT')]
        rows=[row for row in rows if not search or search.casefold() in str(row).casefold()]
        return dict(total=len(rows),rows=rows[offset:offset+limit])

    def leadership_stats(self,mid):
        current=[a for a in self.appointments if a['is_current']]
        return dict(current=len(current),members=len({a['member_id'] for a in current}),vacant=self.list_leadership(mid,'VACANT')['total'],positions=len(self.positions))

    def leadership_audit(self,*_args):
        return [dict(action='MEMBER_ASSIGNED',actor='Preview Administrator',occurred_at=datetime.now(timezone.utc),old_values=None,new_values={})]
