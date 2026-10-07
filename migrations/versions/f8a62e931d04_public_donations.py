"""Add private online donations and backend managed giving purposes.

Revision ID: f8a62e931d04
Revises: e3acdfa4cbf6
"""
from uuid import uuid4
from alembic import op
import sqlalchemy as sa

revision='f8a62e931d04'
down_revision='e3acdfa4cbf6'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('donation_categories',
        sa.Column('id',sa.UUID(),primary_key=True),sa.Column('name',sa.String(100),nullable=False,unique=True),
        sa.Column('is_active',sa.Boolean(),server_default=sa.text('true'),nullable=False),
        sa.Column('display_order',sa.Integer(),server_default='0',nullable=False))
    op.create_table('donations',
        sa.Column('id',sa.UUID(),primary_key=True),sa.Column('request_id',sa.UUID(),nullable=False,unique=True),
        sa.Column('request_hash',sa.String(64),nullable=False),sa.Column('receipt_nonce',sa.UUID(),nullable=False),
        sa.Column('reference',sa.String(64),nullable=False,unique=True),sa.Column('donor_name',sa.String(200),nullable=False),
        sa.Column('email',sa.String(254),nullable=False),sa.Column('phone',sa.String(40),nullable=False),
        sa.Column('amount',sa.Numeric(12,2),nullable=False),sa.Column('currency',sa.String(3),nullable=False),
        sa.Column('category_id',sa.UUID(),sa.ForeignKey('donation_categories.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('category_name',sa.String(100),nullable=False),sa.Column('note',sa.Text(),nullable=False),
        sa.Column('provider',sa.String(20),nullable=False),sa.Column('payment_mode',sa.String(4),server_default='TEST',nullable=False),
        sa.Column('provider_reference',sa.String(64),nullable=False,unique=True),sa.Column('provider_transaction_id',sa.String(100),unique=True),
        sa.Column('authorization_url',sa.String(500)),sa.Column('status',sa.String(30),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column('paid_at',sa.DateTime(timezone=True)),
        sa.CheckConstraint('amount>0',name='ck_donation_positive_amount'),
        sa.CheckConstraint("payment_mode='TEST'",name='ck_donation_test_mode'),
        sa.CheckConstraint("status IN ('INITIALIZING','PENDING','SUCCESS','FAILED','CANCELLED','INITIALIZATION_FAILED')",name='ck_donation_status'),
        sa.CheckConstraint("status!='SUCCESS' OR (paid_at IS NOT NULL AND provider_transaction_id IS NOT NULL)",name='ck_donation_paid'))
    for column in ('category_id','status','created_at'):op.create_index('ix_donations_'+column,'donations',[column])
    bind=op.get_bind()
    categories=sa.table('donation_categories',sa.column('id',sa.UUID()),sa.column('name',sa.String()),sa.column('is_active',sa.Boolean()),sa.column('display_order',sa.Integer()))
    for order,name in enumerate(['General Offering','Tithe','Building / Development','Missions / Outreach','Welfare','Special Contribution','Other']):
        bind.execute(categories.insert().values(id=uuid4(),name=name,is_active=True,display_order=order))
    bind.execute(sa.text("INSERT INTO permissions(id,code,name,module,is_active) VALUES (:id,'DONATIONS_VIEW','View private online donation and donor records','Finance',true) ON CONFLICT(code) DO NOTHING"),{'id':uuid4()})
    bind.execute(sa.text("INSERT INTO role_permissions(role_id,permission_id) SELECT r.id,p.id FROM roles r CROSS JOIN permissions p WHERE r.code IN ('ADMINISTRATOR','FINANCE_OFFICER') AND p.code='DONATIONS_VIEW' ON CONFLICT DO NOTHING"))

def downgrade():
    raise RuntimeError('Donation records are financial history. Restore a reviewed backup instead of dropping them.')
