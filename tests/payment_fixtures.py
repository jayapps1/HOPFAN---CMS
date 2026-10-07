"""Synthetic provider exists only in tests and never calls a payment network."""
from datetime import datetime,timezone
from copy import deepcopy
from src.services.paystack_service import PaystackService,PaymentSettings,PaymentUnavailable

class TestPaystack(PaystackService):
    __test__=False
    def __init__(self,origin='http://localhost:3002'):
        super().__init__(PaymentSettings(secret_key='sk_test_synthetic_fixture',receipt_key='synthetic-receipt-key',public_origin=origin))
        self.transactions={};self.calls=[];self.fail_initialize=False
    def _request(self,path,body=None):
        self.calls.append((path,deepcopy(body)))
        if path=='initialize':
            if self.fail_initialize:raise PaymentUnavailable('Synthetic provider outage')
            reference=body['reference']
            self.transactions[reference]=dict(reference=reference,amount=body['amount'],currency=body['currency'],domain='test',status='pending',id=len(self.transactions)+1,paid_at=datetime.now(timezone.utc).isoformat())
            return dict(reference=reference,authorization_url='https://checkout.paystack.com/'+reference)
        return deepcopy(self.transactions[path.removeprefix('verify/')])
