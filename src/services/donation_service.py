"""Idempotent checkout, authenticated settlement and capability protected receipts."""
from datetime import datetime,timedelta,timezone
import hashlib,hmac,json
from uuid import uuid4
from sqlalchemy import select,func,text
from src.models.donation import Donation,DonationCategory
from src.services.paystack_service import PaymentUnavailable,PaymentMismatch,checkout_url
from src.services.web_security import WebSecurityError


class DonationService:
    def __init__(self,db,provider):self.db,self.provider=db,provider
    def options(self):
        return dict(enabled=self.provider.settings.enabled,mode='test',currency=self.provider.settings.currency,
            categories=[{'id':row.id,'name':row.name} for row in self.db.scalars(select(DonationCategory)
                .where(DonationCategory.is_active.is_(True)).order_by(DonationCategory.display_order,DonationCategory.name,DonationCategory.id))])
    def token(self,row):
        return hmac.new(self.provider.settings.receipt_key.encode(),
            ('donation-receipt\0'+row.reference+'\0'+str(row.receipt_nonce)).encode(),hashlib.sha256).hexdigest()
    def initialized(self,row):
        if row.status=='INITIALIZATION_FAILED':raise PaymentUnavailable('Checkout initialization failed.')
        if row.status=='INITIALIZING' or not row.authorization_url:
            raise WebSecurityError(409,'CHECKOUT_PENDING','Checkout is not ready. Please wait and try again.')
        return dict(reference=row.reference,receipt_token=self.token(row),authorization_url=checkout_url(row.authorization_url))
    def initialize(self,body):
        self.provider.require_enabled()
        normalized=body.model_dump(mode='json',exclude={'request_id'})
        fingerprint=hmac.new(self.provider.settings.receipt_key.encode(),json.dumps(normalized,sort_keys=True).encode(),hashlib.sha256).hexdigest()
        # Serialize concurrent submissions of the same browser attempt across workers.
        key=int.from_bytes(hashlib.sha256(body.request_id.bytes).digest()[:8],byteorder='big',signed=True)
        self.db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':key})
        row=self.db.scalar(select(Donation).where(Donation.request_id==body.request_id))
        if row:
            if not hmac.compare_digest(row.request_hash,fingerprint):raise WebSecurityError(409,'ATTEMPT_CONFLICT','Start a new donation for changed details.')
            result=self.initialized(row);self.db.commit();return result
        category=self.db.scalar(select(DonationCategory).where(DonationCategory.id==body.category_id,DonationCategory.is_active.is_(True)))
        if not category:raise WebSecurityError(422,'VALIDATION_ERROR','Choose a supported donation purpose.')
        reference='HOPFAN-DON-'+uuid4().hex
        row=Donation(request_id=body.request_id,request_hash=fingerprint,reference=reference,provider_reference=reference,
            donor_name=body.donor_name,email=body.email,phone=body.phone,amount=body.amount,
            currency=self.provider.settings.currency,category_id=category.id,category_name=category.name,note=body.note)
        self.db.add(row);self.db.commit();self.db.refresh(row)
        try:url=self.provider.initialize(row)
        except (PaymentUnavailable,PaymentMismatch):
            row=self.locked(reference)
            if row.status=='INITIALIZING':row.status='INITIALIZATION_FAILED'
            self.db.commit();raise
        row=self.locked(reference)
        row.authorization_url=checkout_url(url)
        if row.status=='INITIALIZING':row.status='PENDING'
        self.db.commit();return self.initialized(row)
    def locked(self,reference):
        return self.db.scalar(select(Donation).where(Donation.reference==reference).with_for_update().execution_options(populate_existing=True))
    @staticmethod
    def receipt(row):return dict(reference=row.reference,amount=row.amount,currency=row.currency,purpose=row.category_name,status=row.status,paid_at=row.paid_at)
    def owned(self,reference,token):
        row=self.db.scalar(select(Donation).where(Donation.reference==reference))
        if not row or not token or not self.provider.settings.receipt_key or not hmac.compare_digest(self.token(row),token) or row.created_at<datetime.now(timezone.utc)-timedelta(days=30):
            raise WebSecurityError(404,'RESOURCE_NOT_FOUND','The donation receipt is unavailable in this browser.')
        return row
    def verify(self,reference,token):
        row=self.owned(reference,token)
        if row.status=='SUCCESS':return self.receipt(row)
        data=self.provider.verify(reference)
        row=self.locked(reference)
        self.settle(row,data);self.db.commit();return self.receipt(row)
    def settle(self,row,data):
        if (data.get('reference')!=row.provider_reference or type(data.get('amount')) is not int
                or data['amount']!=int(row.amount*100) or data.get('currency')!=row.currency or data.get('domain')!='test'):
            raise PaymentMismatch('Payment verification did not match the donation.')
        status=data.get('status')
        if status=='success':
            transaction_id=data.get('id')
            if type(transaction_id) not in {str,int} or not str(transaction_id).isdigit() or len(str(transaction_id))>100:raise PaymentMismatch('Invalid provider transaction.')
            try:
                paid_at=datetime.fromisoformat(data['paid_at'].replace('Z','+00:00'))
                if paid_at.tzinfo is None or paid_at>datetime.now(timezone.utc)+timedelta(minutes=5):raise ValueError()
            except (ValueError,TypeError,KeyError,AttributeError):raise PaymentMismatch('Invalid payment timestamp.') from None
            if row.status=='SUCCESS':
                if row.provider_transaction_id!=str(transaction_id):raise PaymentMismatch('Provider transaction changed.')
                return
            row.provider_transaction_id=str(transaction_id);row.status='SUCCESS';row.paid_at=paid_at
        elif row.status!='SUCCESS':
            if status=='failed':row.status='FAILED'
            elif status=='abandoned':row.status='CANCELLED'
            elif status not in {'pending','ongoing','processing','queued'}:raise PaymentMismatch('Unknown payment status.')
    def webhook(self,event):
        if event.get('event')!='charge.success':return
        data=event.get('data')
        if not isinstance(data,dict) or data.get('status')!='success' or not isinstance(data.get('reference'),str):raise PaymentMismatch('Invalid charge event.')
        row=self.locked(data.get('reference'))
        # The account can receive transactions from other applications.
        if not row:return
        self.settle(row,data);self.db.commit()
    def finance(self,page,page_size):
        stmt=select(Donation)
        total=self.db.scalar(select(func.count()).select_from(Donation))
        rows=self.db.scalars(stmt.order_by(Donation.created_at.desc(),Donation.id).limit(page_size).offset((page-1)*page_size)).all()
        return dict(items=[dict(self.receipt(row),id=row.id,donor_name=row.donor_name,email=row.email,phone=row.phone,note=row.note,
            provider=row.provider,provider_reference=row.provider_reference,created_at=row.created_at) for row in rows],
            total=total,page=page,page_size=page_size,pages=(total+page_size-1)//page_size)
