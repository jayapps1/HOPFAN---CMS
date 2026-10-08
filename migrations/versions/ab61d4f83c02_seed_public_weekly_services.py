"""Seed the explicitly approved weekly schedule without overwriting edits.
Revision ID: ab61d4f83c02
Revises: f8a62e931d04
"""
from copy import deepcopy
from datetime import datetime,timezone
from uuid import uuid5,NAMESPACE_URL
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op
revision='ab61d4f83c02'
down_revision='f8a62e931d04'
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind()
    table=sa.table('website_settings',sa.column('id',sa.Integer()),sa.column('draft_data',JSONB()),sa.column('published_data',JSONB()),sa.column('updated_at',sa.DateTime(timezone=True)),sa.column('published_at',sa.DateTime(timezone=True)))
    row=bind.execute(sa.select(table).where(table.c.id==1).with_for_update()).mappings().first()
    if row and ((row['draft_data'] or {}).get('service_times') or (row['published_data'] or {}).get('service_times')):return
    stamp=datetime.now(timezone.utc)
    services=[]
    for order,(name,day,start,end) in enumerate([('Sunday Service','SUNDAY','07:00','10:00'),('Wednesday Service','WEDNESDAY','09:00','12:00'),('Friday Evening Service','FRIDAY','18:30','21:00')]):
        services.append(dict(id=str(uuid5(NAMESPACE_URL,'hopfan-weekly-service:'+day)),name=name,day_of_week=day,start_time=start,end_time=end,schedule='',description='',location='',display_order=order,active=True,featured=True,created_at=stamp.isoformat(),updated_at=stamp.isoformat()))
    # An unpublished contact/settings draft must never be released as a side effect.
    published=deepcopy(row['published_data']) if row and row['published_data'] else dict(church_name='HOPFAN',full_name='House of Prayer for All Nations')
    draft=deepcopy(row['draft_data']) if row else deepcopy(published)
    for data in (draft,published):
        data['service_times']=deepcopy(services)
        data.setdefault('timezone','UTC')
    if row:bind.execute(table.update().where(table.c.id==1).values(draft_data=draft,published_data=published,updated_at=stamp,published_at=stamp))
    else:bind.execute(table.insert().values(id=1,draft_data=draft,published_data=published,updated_at=stamp,published_at=stamp))

def downgrade():
    # Keep editable administrator-owned configuration and approved service data.
    pass
