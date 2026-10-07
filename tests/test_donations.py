"""Money validation, isolated TEST checkout, ownership and idempotent settlement."""
from datetime import datetime,timedelta,timezone
from dataclasses import replace
from uuid import uuid4
import hashlib,hmac,json
import pytest
from sqlalchemy import select,func
from src.models import Donation,DonationCategory,ContentEntry
from src.services.paystack_service import PaymentSettings,checkout_url,PaymentUnavailable
from src.services.public_site_service import PublicSiteService
from tests.payment_fixtures import TestPaystack
from tests.test_web_auth import security_database,credential_hash,environment,client,login,ORIGIN

@pytest.fixture
def payments(environment):
    provider=TestPaystack();environment.app.state.payment_provider=provider
    with environment.factory() as db:
        category=DonationCategory(name='Reviewed offering',display_order=1);db.add(category);db.commit()
        environment.category_id=category.id
    environment.provider=provider
    return environment

def body(payments,**changes):
    return dict(request_id=str(uuid4()),donor_name='PRIVATE-DONOR',email='private-donor@example.invalid',phone='+233 200 000 001',category_id=str(payments.category_id),amount='125.50',note='PRIVATE-DONOR-NOTE',**changes)
def initialize(client,payments,data=None):
    response=client.post('/api/v1/public/donations',json=data or body(payments),headers={'Origin':ORIGIN})
    assert response.status_code==201,response.text
    return response.json()
def verify(client,row):return client.post('/api/v1/public/donations/'+row['reference']+'/verify',headers={'Origin':ORIGIN},json={'receipt_token':row['receipt_token']})
def webhook(client,payments,data=None,signature=None):
    event={'event':'charge.success','data':data or {}}
    raw=json.dumps(event,separators=(',',':')).encode()
    signature=signature or hmac.new(payments.provider.settings.secret_key.encode(),raw,hashlib.sha512).hexdigest()
    return client.post('/api/v1/payments/paystack/webhook',content=raw,headers={'Content-Type':'application/json','X-Paystack-Signature':signature})

def test_initialize_persists_and_same_attempt_only_initializes_once(payments,client):
    data=body(payments);row=initialize(client,payments,data);again=initialize(client,payments,data)
    assert row==again
    assert len(payments.provider.calls)==1
    call=payments.provider.calls[0][1]
    assert call['amount']==12550 and call['currency']=='GHS'
    assert call['callback_url'].endswith('/donate/result') and row['reference'] in call['metadata']['cancel_action']
    with payments.factory() as db:
        assert db.scalar(select(func.count()).select_from(Donation))==1
        saved=db.scalar(select(Donation));assert saved.status=='PENDING' and saved.email==data['email'] and saved.note==data['note']
    assert 'PRIVATE-' not in json.dumps(row)
    assert client.post('/api/v1/public/donations',json=dict(data,amount='126'),headers={'Origin':ORIGIN}).status_code==409

@pytest.mark.parametrize('field,value',[('amount','0'),('amount','-1'),('amount','NaN'),('amount','0.001'),('amount','1000001'),('email','bad-email'),('phone','not-a-phone'),('phone','123'),('donor_name',' '),('category_id',str(uuid4()))])
def test_server_rejects_invalid_donations(payments,client,field,value):
    data=body(payments);data[field]=value
    response=client.post('/api/v1/public/donations',json=data,headers={'Origin':ORIGIN})
    assert response.status_code==422,response.text
    assert payments.provider.calls==[]
    with payments.factory() as db:assert db.scalar(select(func.count()).select_from(Donation))==0

def test_checkout_configuration_is_test_only_and_closed_without_key(payments,client):
    with pytest.raises(ValueError):PaymentSettings(secret_key='sk_live_unacceptable')
    payments.provider.settings=replace(payments.provider.settings,secret_key='')
    assert client.get('/api/v1/public/donations/options').json()['enabled'] is False
    assert client.post('/api/v1/public/donations',json=body(payments),headers={'Origin':ORIGIN}).status_code==503
    assert payments.provider.calls==[]

def test_category_options_are_dynamic_and_exclude_inactive(payments,client):
    with payments.factory() as db:
        db.add(DonationCategory(name='Inactive purpose',is_active=False));db.commit()
    result=client.get('/api/v1/public/donations/options').json()
    assert result['categories']==[{'id':str(payments.category_id),'name':'Reviewed offering'}]

def test_receipt_cannot_be_read_or_verified_by_reference_alone(payments,client):
    row=initialize(client,payments);path='/api/v1/public/donations/'+row['reference']
    assert client.get(path).status_code==404
    assert client.get(path,headers={'X-Donation-Token':'0'*64}).status_code==404
    result=client.get(path,headers={'X-Donation-Token':row['receipt_token']})
    assert result.status_code==200 and 'PRIVATE-' not in result.text
    assert set(result.json())=={'reference','amount','currency','purpose','status','paid_at'}
    assert client.post(path+'/verify',json={'receipt_token':'0'*64},headers={'Origin':ORIGIN}).status_code==404
    with payments.factory() as db:
        saved=db.scalar(select(Donation));saved.created_at=datetime.now(timezone.utc)-timedelta(days=31);db.commit()
    assert client.get(path,headers={'X-Donation-Token':row['receipt_token']}).status_code==404

@pytest.mark.parametrize('status,expected',[('success','SUCCESS'),('failed','FAILED'),('abandoned','CANCELLED'),('pending','PENDING')])
def test_verified_results_and_duplicate_callbacks(payments,client,status,expected):
    row=initialize(client,payments);payments.provider.transactions[row['reference']]['status']=status
    response=verify(client,row);assert response.status_code==200,response.text
    assert response.json()['status']==expected and 'PRIVATE-' not in response.text
    assert verify(client,row).json()==response.json()
    with payments.factory() as db:assert db.scalar(select(func.count()).select_from(Donation))==1

@pytest.mark.parametrize('field,value',[('amount',1),('currency','NGN'),('domain','live'),('reference','wrong-reference'),('paid_at','invalid')])
def test_provider_amount_currency_domain_reference_and_timestamp_must_match(payments,client,field,value):
    row=initialize(client,payments);data=payments.provider.transactions[row['reference']];data['status']='success';data[field]=value
    assert verify(client,row).status_code==409
    with payments.factory() as db:assert db.scalar(select(Donation)).status=='PENDING'

def test_signed_webhooks_are_idempotent_and_success_does_not_regress(payments,client):
    row=initialize(client,payments);data=payments.provider.transactions[row['reference']];data['status']='success'
    assert webhook(client,payments,data,signature='0'*128).status_code==401
    assert webhook(client,payments,data).status_code==200
    assert webhook(client,payments,data).status_code==200
    data['status']='failed'
    assert verify(client,row).json()['status']=='SUCCESS'
    with payments.factory() as db:
        assert db.scalar(select(func.count()).select_from(Donation))==1
        saved=db.scalar(select(Donation));assert saved.paid_at and saved.provider_transaction_id

def test_donor_records_require_explicit_finance_permission(payments,client):
    initialize(client,payments)
    assert client.get('/api/v1/finance/donations').status_code==401
    assert login(client,'youth').status_code==200
    assert client.get('/api/v1/finance/donations').status_code==403
    assert login(client,'admin').status_code==200
    response=client.get('/api/v1/finance/donations');assert response.status_code==200
    assert response.json()['items'][0]['email']=='private-donor@example.invalid'

def test_untrusted_origins_are_rejected_and_init_errors_are_persisted(payments,client):
    data=body(payments)
    assert client.post('/api/v1/public/donations',json=data).status_code==403
    assert client.post('/api/v1/public/donations',json=data,headers={'Origin':'https://untrusted.invalid'}).status_code==403
    payments.provider.fail_initialize=True
    assert client.post('/api/v1/public/donations',json=data,headers={'Origin':ORIGIN}).status_code==503
    with payments.factory() as db:assert db.scalar(select(Donation)).status=='INITIALIZATION_FAILED'
    assert client.post('/api/v1/public/donations',json=data,headers={'Origin':ORIGIN}).status_code==503
    payments.provider.fail_initialize=False
    assert initialize(client,payments)['reference']

@pytest.mark.parametrize('url',['http://checkout.paystack.com/x','https://evil.invalid/x','https://checkout.paystack.com.evil.invalid/x','https://checkout.paystack.com/x?redirect=evil','https://user@checkout.paystack.com/x'])
def test_only_approved_checkout_urls_are_accepted(url):
    with pytest.raises(PaymentUnavailable):checkout_url(url)

def test_home_has_eight_ordered_published_leaders_and_full_list_is_paginated(payments):
    with payments.factory() as db:
        for index in reversed(range(12)):
            slug='synthetic-'+str(index).zfill(2)
            data=dict(slug=slug,title=slug,summary='Approved public profile',data={'public_name':'Synthetic '+str(index),'public_title':'Published role','display_order':index})
            db.add(ContentEntry(kind='LEADERSHIP',slug=slug,title=slug,draft_data=dict(data,data={'display_order':999}),published_data=data if index<11 else None,status='PUBLISHED' if index<11 else 'DRAFT',published_at=datetime.now(timezone.utc)))
        db.commit();service=PublicSiteService(db)
        assert [row['slug'] for row in service.site()['leadership']]==['synthetic-'+str(index).zfill(2) for index in range(8)]
        first=service.list_content('LEADERSHIP',limit=6);second=service.list_content('LEADERSHIP',limit=6,offset=6)
        assert first['total']==11 and len(first['rows'])==6 and len(second['rows'])==5
        assert first['rows'][0]['slug']=='synthetic-00' and second['rows'][0]['slug']=='synthetic-06'


def test_concurrent_submissions_have_one_checkout_and_one_record(payments):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from src.api.schemas.donation import DonationWrite
    from src.services.donation_service import DonationService
    from src.services.web_security import WebSecurityError
    entered,release=Event(),Event()
    provider=payments.provider
    original=provider.initialize
    def pause(row):
        entered.set()
        assert release.wait(10)
        return original(row)
    provider.initialize=pause
    data=DonationWrite.model_validate(body(payments))
    def submit():
        with payments.factory() as db:return DonationService(db,provider).initialize(data)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(submit)
        try:
            assert entered.wait(10)
            second=pool.submit(submit)
            with pytest.raises(WebSecurityError) as caught:second.result(timeout=10)
            assert caught.value.code=='CHECKOUT_PENDING'
        finally:release.set()
        assert first.result(timeout=10)['reference']
    assert len(provider.calls)==1
    with payments.factory() as db:assert db.scalar(select(func.count()).select_from(Donation))==1


def test_concurrent_signed_settlement_does_not_duplicate_payment(payments,client):
    from concurrent.futures import ThreadPoolExecutor
    from src.services.donation_service import DonationService
    row=initialize(client,payments);data=payments.provider.transactions[row['reference']];data['status']='success'
    def settle():
        with payments.factory() as db:DonationService(db,payments.provider).webhook({'event':'charge.success','data':data})
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda _:settle(),range(2)))
    with payments.factory() as db:
        assert db.scalar(select(func.count()).select_from(Donation))==1
        assert db.scalar(select(Donation)).status=='SUCCESS'
