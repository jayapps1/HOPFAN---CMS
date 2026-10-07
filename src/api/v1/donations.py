"""Anonymous giving and a separate, permission checked finance projection."""
from contextlib import contextmanager
import json
from typing import Annotated
from fastapi import APIRouter,Depends,Request,Header,Query,Path
from sqlalchemy.exc import SQLAlchemyError,IntegrityError
from src.api.dependencies import get_db,require_permission
from src.api.security.csrf import require_trusted_origin
from src.api.schemas.donation import DonationWrite,DonationOptions,DonationInitialized,ReceiptRequest,DonationReceipt,DonationRecord
from src.api.schemas.workspace import Page
from src.api.v1 import API_PREFIX
from src.services.paystack_service import PaymentSettings,PaystackService,PaymentUnavailable,PaymentMismatch
from src.services.donation_service import DonationService
from src.services.web_rate_limit_service import WebRateLimitService
from src.services.web_security import WebSecurityError

router=APIRouter(prefix=API_PREFIX,tags=['Donations'])
DB=Annotated[object,Depends(get_db,scope='function')]
Origin=Annotated[None,Depends(require_trusted_origin)]
Reference=Annotated[str,Path(pattern=r'^HOPFAN-DON-[a-f0-9]{32}$')]

@contextmanager
def safe_payment_errors():
    try:yield
    except (PaymentUnavailable,ValueError):raise WebSecurityError(503,'PAYMENT_UNAVAILABLE','Online checkout is temporarily unavailable. Please contact the church or try again later.') from None
    except PaymentMismatch:raise WebSecurityError(409,'PAYMENT_UNCONFIRMED','The payment could not be confirmed. Please contact the church with your reference.') from None
    except IntegrityError:raise WebSecurityError(409,'PAYMENT_CONFLICT','This payment is being processed. Please check its status shortly.') from None
    except SQLAlchemyError:raise WebSecurityError(503,'DATABASE_UNAVAILABLE','HOPFAN is temporarily unavailable.') from None

def service(request:Request,db:DB):
    with safe_payment_errors():
        provider=getattr(request.app.state,'payment_provider',None) or PaystackService(PaymentSettings.from_environment(request.app.state.settings))
        yield DonationService(db,provider)
Service=Annotated[DonationService,Depends(service,scope='function')]
def rate(service,request,kind,limit):
    WebRateLimitService.consume(service.db,[(kind,request.client.host if request.client else 'unknown',limit,60)])

@router.get('/public/donations/options',response_model=DonationOptions)
def options(service:Service):return service.options()
@router.post('/public/donations',response_model=DonationInitialized,status_code=201)
def initialize(request:Request,service:Service,origin:Origin,body:DonationWrite):
    rate(service,request,'donation-init',10)
    return service.initialize(body)
@router.get('/public/donations/{reference}',response_model=DonationReceipt)
def receipt(reference:Reference,request:Request,service:Service,x_donation_token:Annotated[str,Header(max_length=64,pattern=r'^(?:[0-9a-f]{64})?$')]=''):
    rate(service,request,'donation-receipt',60)
    return service.receipt(service.owned(reference,x_donation_token))
@router.post('/public/donations/{reference}/verify',response_model=DonationReceipt)
def verify(reference:Reference,request:Request,service:Service,origin:Origin,body:ReceiptRequest):
    rate(service,request,'donation-verify',20)
    return service.verify(reference,body.receipt_token)
@router.post('/payments/paystack/webhook')
async def webhook(request:Request,service:Service):
    raw=await request.body()
    if len(raw)>262144:raise WebSecurityError(413,'REQUEST_TOO_LARGE','The request exceeds the allowed size.')
    if not service.provider.authentic_webhook(raw,request.headers.get('x-paystack-signature')):
        raise WebSecurityError(401,'INVALID_SIGNATURE','Invalid webhook signature.')
    try:event=json.loads(raw)
    except (ValueError,UnicodeError):raise WebSecurityError(400,'INVALID_WEBHOOK','Invalid webhook.') from None
    if not isinstance(event,dict):raise WebSecurityError(400,'INVALID_WEBHOOK','Invalid webhook.')
    # Sync settlement runs in the worker pool, never blocking the event loop.
    from starlette.concurrency import run_in_threadpool
    await run_in_threadpool(service.webhook,event)
    return {'received':True}
@router.get('/finance/donations',response_model=Page[DonationRecord],dependencies=[Depends(require_permission('DONATIONS_VIEW'))])
def finance(service:Service,page_number:Annotated[int,Query(ge=1,le=100000)]=1,page_size:Annotated[int,Query(ge=1,le=100)]=25):
    return service.finance(page_number,page_size)
