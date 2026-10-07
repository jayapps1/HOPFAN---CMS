"""The single backend Paystack adapter. No provider credentials reach the browser."""
from dataclasses import dataclass,field
import hashlib,hmac,json,os,re
from urllib.parse import urlsplit,quote
from urllib.request import Request,build_opener,HTTPRedirectHandler
from src.config.environment import load_environment


class PaymentUnavailable(Exception):pass
class PaymentMismatch(Exception):pass


@dataclass(frozen=True)
class PaymentSettings:
    secret_key:str=field(default='',repr=False)
    receipt_key:str=field(default='',repr=False)
    currency:str='GHS'
    public_origin:str='http://localhost:3000'
    app_env:str='development'

    def __post_init__(self):
        # This release deliberately supports TEST checkout only.
        if self.secret_key and not re.fullmatch(r'sk_test_[A-Za-z0-9_-]+',self.secret_key):
            raise ValueError('PAYSTACK_SECRET_KEY must be a Paystack TEST secret key.')
        if self.currency not in {'GHS','NGN','KES','ZAR','USD'}:raise ValueError('Choose a supported PAYSTACK_CURRENCY.')
        from src.config.online_settings import _validate_origin
        _validate_origin(self.public_origin,require_https=self.app_env!='development')

    @property
    def enabled(self):return bool(self.secret_key and self.receipt_key and self.public_origin)

    @classmethod
    def from_environment(cls,settings):
        load_environment()
        return cls(secret_key=os.getenv('PAYSTACK_SECRET_KEY',''),receipt_key=os.getenv('APP_ENCRYPTION_KEY',''),
            currency=os.getenv('PAYSTACK_CURRENCY','GHS').upper(),public_origin=settings.web_public_origin,app_env=settings.app_env)


def checkout_url(value):
    try:
        url=urlsplit(value)
        valid=url.scheme=='https' and url.hostname=='checkout.paystack.com' and url.port in {None,443} and not url.username and not url.password
        valid=valid and bool(re.fullmatch(r'/[A-Za-z0-9_-]+',url.path)) and not url.query and not url.fragment
        if valid:return value
    except (ValueError,TypeError):pass
    raise PaymentUnavailable('Checkout is unavailable.')


class PaystackService:
    def __init__(self,settings):self.settings=settings
    def require_enabled(self):
        if not self.settings.enabled:raise PaymentUnavailable('Online checkout is not configured.')
    def _request(self,path,body=None):
        self.require_enabled()
        request=Request('https://api.paystack.co/transaction/'+path,
            data=json.dumps(body).encode('utf-8') if body is not None else None,
            headers={'Authorization':'Bearer '+self.settings.secret_key,'Content-Type':'application/json','Accept':'application/json'})
        try:
            class NoRedirect(HTTPRedirectHandler):
                def redirect_request(self,*args,**kwargs):return None
            with build_opener(NoRedirect()).open(request,timeout=10) as response:
                # Never log or retain the full provider response (payment instrument data).
                raw=response.read(262145)
                if len(raw)>262144:raise ValueError()
                result=json.loads(raw)
            if result.get('status') is not True or not isinstance(result.get('data'),dict):raise ValueError()
            return result['data']
        except Exception:raise PaymentUnavailable('Payment service is temporarily unavailable.') from None
    def initialize(self,row):
        data=self._request('initialize',{'email':row.email,'amount':int(row.amount*100),'currency':row.currency,
            'reference':row.reference,'callback_url':self.settings.public_origin+'/donate/result',
            'metadata':{'donation_reference':row.reference,'cancel_action':self.settings.public_origin+'/donate/result?reference='+row.reference+'&cancelled=1'}})
        if data.get('reference')!=row.reference:raise PaymentMismatch('Payment reference did not match.')
        return checkout_url(data.get('authorization_url'))
    def verify(self,reference):return self._request('verify/'+quote(reference,safe=''))
    def authentic_webhook(self,raw,signature):
        self.require_enabled()
        expected=hmac.new(self.settings.secret_key.encode(),raw,hashlib.sha512).hexdigest()
        return isinstance(signature,str) and bool(re.fullmatch(r'[0-9a-f]{128}',signature)) and hmac.compare_digest(expected,signature)
