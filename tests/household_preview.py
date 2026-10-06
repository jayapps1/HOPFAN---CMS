"""Synthetic family fixtures for desktop testing; never connects to church data."""
from datetime import date, datetime, timezone
import uuid
from src.security.household_permissions import RELATIONSHIPS
from src.services.household_service import HouseholdService, HouseholdServiceError, HouseholdMoveRequired, HouseholdHeadConflict, age_on


class PreviewHouseholdService:
    def __init__(self, count=30, management=True, view_all=True):
        self.management, self.view_all = management, view_all
        self.households, self.links, self.events = [], [], []
        self.members = [dict(id=str(uuid.uuid4()), full_name=name, first_name=name.split()[0], last_name='Owusu',
            member_no=f'PREVIEW-FAMILY-{index+1:04d}', phone='054 000 0000', email=f'family{index}@example.invalid',
            photo_path='', date_of_birth=date(2016,6,14) if index==2 else date(1990,1,1) if index<2 else None,
            status='ACTIVE') for index,name in enumerate(['Daniel Owusu','Ama Owusu','Joseph Owusu','Grace Owusu']+
                [f'Synthetic Member {index}' for index in range(31)])]
        for index in range(count):
            self.create_household(dict(household_name='Owusu Household' if index==0 else 'Synthetic Family '+str(index), primary_phone='054 000 0000'))
        if count:
            for index,relationship in enumerate(('HEAD','SPOUSE','SON','DEPENDANT')):
                self.add_member(self.households[0]['id'], self.members[index]['id'], relationship, joined_at=date(2020,1,1))

    def capabilities(self):
        return dict(view=True, view_all=self.view_all, **{name:self.management for name in
            ('create','edit','archive','delete','remove_member','add_member','create_member')}, member_search=self.view_all)

    def _event(self, hid, action, old=None, new=None):
        self.events.append(dict(id=str(uuid.uuid4()), household_id=hid, action=action, actor='Synthetic administrator',
            occurred_at=datetime.now(timezone.utc), old_values=old, new_values=new, member_id=None))

    def _current(self, hid): return [link for link in self.links if link['household_id']==hid and link['is_active']]
    def _household(self, hid): return next(h for h in self.households if h['id']==hid)
    def _member(self, mid): return next(m for m in self.members if m['id']==mid)

    def _link_dto(self, link):
        member = self._member(link['member_id'])
        return dict(link, full_name=member['full_name'], member_no=member['member_no'], photo_path=member['photo_path'],
            phone=member['phone'], email=member['email'], member_status=member['status'], date_of_birth=member['date_of_birth'],
            age=age_on(member['date_of_birth']), relationship_label=RELATIONSHIPS[link['relationship']])

    def create_household(self, data, head_member_id=None, **kwargs):
        values = HouseholdService._values(data)
        row = dict(values, id=str(uuid.uuid4()), household_code=f'PREVIEW-HH-{len(self.households)+1:04d}',
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc), archived_at=None)
        for key in ('notes','primary_address','primary_phone'): row[key] = row[key] or ''
        self.households.append(row)
        if head_member_id:
            try: self.add_member(row['id'], head_member_id, 'HEAD', joined_at=date.today(), **kwargs)
            except Exception:
                self.households.remove(row); raise
        self._event(row['id'], 'HOUSEHOLD_CREATED', new={'household_name':row['household_name']})
        return self.get_household(row['id'])

    def update_household(self, hid, data, _expected=None):
        row = self._household(hid); row.update(HouseholdService._values(data), updated_at=datetime.now(timezone.utc))
        for key in ('notes','primary_address','primary_phone'): row[key] = row[key] or ''
        self._event(hid, 'HOUSEHOLD_EDITED', new={'household_name':row['household_name']})

    def get_household(self, hid):
        row = self._household(hid)
        links = self._current(hid)
        head = next((link for link in links if link['is_household_head']), None)
        ages = [age_on(self._member(link['member_id'])['date_of_birth']) for link in links]
        stats = dict(total=len(links), adults=sum(age is not None and age>=18 for age in ages),
            children=sum(age is not None and age<18 for age in ages), dependants=sum(link['relationship']=='DEPENDANT' for link in links),
            unknown_age=ages.count(None), active=len(links), inactive=0)
        return dict(row, head_name=self._member(head['member_id'])['full_name'] if head else '',
            head_member_id=head['member_id'] if head else None, head_membership_id=head['id'] if head else None,
            head_updated_at=head['updated_at'] if head else None, member_count=len(links), stats=stats,
            has_history=any(link['household_id']==hid for link in self.links))

    def list_households(self, search='', status='ACTIVE', limit=25, offset=0):
        rows = [self.get_household(row['id']) for row in self.households if status.upper()=='ALL' or row['status']==status.upper()]
        if search:
            rows = [row for row in rows if search.casefold() in (row['household_name']+' '+row['primary_phone']+' '+row['head_name']).casefold()]
        return dict(total=len(rows), rows=rows[offset:offset+limit])

    def get_household_stats(self):
        members = {link['member_id'] for link in self.links if link['is_active']}
        return dict(total=len(self.households), active=sum(h['status']=='ACTIVE' for h in self.households), members=len(members),
            without=len(self.members)-len(members) if self.view_all else None)

    def get_household_members(self, hid, history=False, limit=20, offset=0):
        rows = [self._link_dto(link) for link in self.links if link['household_id']==hid and link['is_active']!=history]
        return dict(total=len(rows), rows=rows[offset:offset+limit])

    def candidate_members(self, search='', unassigned_only=False, limit=20, offset=0):
        rows = []
        for member in self.members:
            link = next((link for link in self.links if link['member_id']==member['id'] and link['is_active']), None)
            if unassigned_only and link: continue
            if search.casefold() not in (member['full_name']+' '+member['member_no']+' '+member['phone']+' '+member['email']).casefold(): continue
            rows.append(dict(member, member_status=member['status'], household_name=self._household(link['household_id'])['household_name'] if link else '',
                current_membership_id=link['id'] if link else None))
        return dict(total=len(rows), rows=rows[offset:offset+limit])

    def add_member(self, hid, mid, relationship, is_household_head=False, joined_at=None, notes='',
            move_from_membership_id=None, replace_head_id=None, **_kwargs):
        relationship = HouseholdService._relationship(relationship, is_household_head)
        current = next((link for link in self.links if link['member_id']==mid and link['is_active']), None)
        head = next((link for link in self._current(hid) if link['is_household_head']), None)
        if current:
            if current['household_id']==hid: raise HouseholdServiceError('This member already belongs to this household.')
            if move_from_membership_id!=current['id']:
                raise HouseholdMoveRequired(dict(id=current['id'], household_name=self._household(current['household_id'])['household_name'],
                    household_id=current['household_id'], updated_at=current['updated_at']))
        if relationship=='HEAD' and head and replace_head_id!=head['id']:
            raise HouseholdHeadConflict(dict(id=head['id'], full_name=self._member(head['member_id'])['full_name'], updated_at=head['updated_at']))
        if current: current.update(is_active=False, left_at=joined_at)
        if relationship=='HEAD' and head: head.update(relationship='RELATIVE', is_household_head=False)
        link = dict(id=str(uuid.uuid4()), household_id=hid, member_id=mid, relationship=relationship,
            is_household_head=relationship=='HEAD', joined_at=joined_at, left_at=None, is_active=True, notes=notes,
            updated_at=datetime.now(timezone.utc))
        self.links.append(link); self._event(hid, 'HOUSEHOLD_MEMBER_ADDED', new={'relationship':relationship})
        return self._link_dto(link)

    def remove_member(self, lid, effective, reason='', _expected=None):
        link = next(link for link in self.links if link['id']==lid)
        link.update(is_active=False, left_at=effective, notes=reason, updated_at=datetime.now(timezone.utc))
        self._event(link['household_id'], 'HOUSEHOLD_MEMBER_REMOVED')

    def update_relationship(self, lid, relationship, notes='', _expected=None):
        link = next(link for link in self.links if link['id']==lid)
        link.update(relationship=relationship, notes=notes, updated_at=datetime.now(timezone.utc))

    def change_household_head(self, hid, lid, previous_relationship='RELATIVE', **_kwargs):
        for link in self._current(hid):
            if link['is_household_head']: link.update(is_household_head=False, relationship=previous_relationship)
            if link['id']==lid: link.update(is_household_head=True, relationship='HEAD')
        self._event(hid, 'HOUSEHOLD_HEAD_CHANGED')

    def archive_household(self, hid, effective=None, _expected=None):
        for link in self._current(hid): link.update(is_active=False, left_at=effective or date.today())
        self._household(hid).update(status='ARCHIVED', archived_at=datetime.now(timezone.utc))
        self._event(hid, 'HOUSEHOLD_ARCHIVED')

    def restore_household(self, hid, _expected=None):
        self._household(hid).update(status='ACTIVE', archived_at=None)

    def delete_unused_household(self, hid, **_kwargs):
        if any(link['household_id']==hid for link in self.links): raise HouseholdServiceError('This household has history.')
        self.households.remove(self._household(hid))

    def audit_events(self, hid, limit=20, offset=0):
        rows = [event for event in self.events if event['household_id']==hid]
        return dict(total=len(rows), rows=rows[offset:offset+limit])


class PreviewFamilyMemberService:
    def __init__(self, service): self.service = service
    def list_ministries(self, member_id=None): return []
    def create_member(self, data, _ministries=None):
        member = dict(data, id=str(uuid.uuid4()), member_no=f'PREVIEW-NEW-{len(self.service.members):04d}',
            full_name=data['first_name']+' '+data['last_name'], photo_path='')
        for key in ('date_of_birth','date_joined','baptism_date'):
            member[key] = date.fromisoformat(member[key]) if member.get(key) else None
        self.service.members.append(member)
        return self.get_member(member['id'])
    def get_member(self, mid):
        member = self.service._member(mid)
        current = next((link for link in self.service.links if link['member_id']==mid and link['is_active']), None)
        household = self.service.get_household(current['household_id']) if current else None
        if household: household['relationship_label'] = RELATIONSHIPS[current['relationship']]
        return dict(member, gender=member.get('gender') or '', marital_status=member.get('marital_status') or '',
            address=member.get('address') or '', alternate_phone=member.get('alternate_phone') or '',
            occupation=member.get('occupation') or '', date_joined=member.get('date_joined'), baptized=member.get('baptized',False),
            baptism_date=member.get('baptism_date'), ministries=[], ministry_ids=[], leadership=[], household=household)
    def set_photo(self, _mid, _path): pass
