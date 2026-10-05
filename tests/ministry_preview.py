"""Synthetic ministry data for desktop-only interaction checks."""
from datetime import datetime,timezone
import uuid
from src.services.ministry_service import MinistryService,MinistryServiceError


class PreviewMinistryService:
    _validate=staticmethod(MinistryService._validate)

    def __init__(self,management=True,count=28):
        self.management=management
        self.rows=[]
        self.changes=[]
        for index in range(count):
            status='INACTIVE' if index==count-2 else 'ARCHIVED' if index==count-1 else 'ACTIVE'
            self.rows.append(self.row('Youth Ministry' if index==0 else f'Ministry {index+1}',
                'YOUTH' if index==0 else f'MINISTRY_{index+1}',status=status,members=2 if index==0 else 0))

    @staticmethod
    def row(name,code,status='ACTIVE',members=0,category='MINISTRY',description='Synthetic ministry description.'):
        now=datetime.now(timezone.utc)
        return dict(id=str(uuid.uuid4()),name=name,code=code,category=category,description=description,status=status,
            is_active=status=='ACTIVE',created_at=now,updated_at=now,archived_at=now if status=='ARCHIVED' else None,
            member_count=members,active_member_count=members,in_use=bool(members),dependencies=['member_ministries'] if members else [])

    def visible(self):
        return self.rows if self.management else self.rows[:1]

    def capabilities(self):
        return dict(view_all=self.management,**{key:self.management for key in ('create','edit','deactivate','archive','restore','delete_unused')})

    def get_ministry_stats(self):
        rows=self.visible()
        return dict(total=len(rows),active=sum(row['status']=='ACTIVE' for row in rows),
            inactive=sum(row['status']=='INACTIVE' for row in rows),archived=sum(row['status']=='ARCHIVED' for row in rows))

    def list_ministries(self,search='',status='ALL',category='ALL',limit=20,offset=0):
        rows=[dict(row) for row in self.visible() if (not search or search.lower() in (row['name']+' '+row['code']).lower())
            and (status=='ALL' or row['status']==status) and (category=='ALL' or row['category']==category)]
        rows.sort(key=lambda row:row['name'])
        return dict(total=len(rows),rows=rows[offset:offset+limit])

    def get_ministry(self,ministry_id):
        return dict(next(row for row in self.rows if row['id']==ministry_id))

    def audit_history(self,_ministry_id):
        return [dict(action='CREATED',actor='Preview Administrator',occurred_at=datetime.now(timezone.utc),
            old_values=None,new_values=dict(name='Synthetic ministry'))]

    def create_ministry(self,data):
        values=self._validate(data)
        row=self.row(**values,status=data.get('status','ACTIVE'))
        self.rows.append(row)
        self.changes.append(('created',row['id']))
        return dict(row)

    def update_ministry(self,ministry_id,data,expected_updated_at=None):
        row=next(row for row in self.rows if row['id']==ministry_id)
        row.update(self._validate(data),status=data['status'],updated_at=datetime.now(timezone.utc))
        self.changes.append(('edited',ministry_id))
        return dict(row)

    def change(self,ministry_id,status):
        row=next(row for row in self.rows if row['id']==ministry_id)
        row.update(status=status,is_active=status=='ACTIVE',archived_at=datetime.now(timezone.utc) if status=='ARCHIVED' else None,
            updated_at=datetime.now(timezone.utc))
        self.changes.append((status,ministry_id))
        return dict(row)

    def activate_ministry(self,ministry_id,expected_updated_at=None):
        return self.change(ministry_id,'ACTIVE')

    def deactivate_ministry(self,ministry_id,expected_updated_at=None):
        return self.change(ministry_id,'INACTIVE')

    def archive_ministry(self,ministry_id,expected_updated_at=None):
        return self.change(ministry_id,'ARCHIVED')

    def restore_ministry(self,ministry_id,status='INACTIVE',expected_updated_at=None):
        return self.change(ministry_id,status)

    def delete_unused_ministry(self,ministry_id,confirmed=False,expected_updated_at=None):
        row=next(row for row in self.rows if row['id']==ministry_id)
        if row['in_use'] or not confirmed:
            raise MinistryServiceError('This ministry cannot be permanently deleted because it has related church records. Archive it instead.')
        self.rows.remove(row)
        self.changes.append(('deleted',ministry_id))
