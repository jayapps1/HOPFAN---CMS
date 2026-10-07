import re
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field,field_validator


class DonationWrite(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    request_id:UUID
    donor_name:str=Field(min_length=1,max_length=200)
    email:str=Field(min_length=3,max_length=254)
    phone:str=Field(default='',max_length=40)
    category_id:UUID
    amount:Decimal=Field(gt=0,le=1000000,max_digits=12,decimal_places=2,allow_inf_nan=False)
    note:str=Field(default='',max_length=2000)
    @field_validator('email')
    @classmethod
    def email_format(cls,value):
        if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+",value):
            raise ValueError('Enter a valid email address.')
        return value.casefold()
    @field_validator('phone')
    @classmethod
    def phone_format(cls,value):
        if value and (not re.fullmatch(r'\+?[0-9 ()-]+',value) or not 7<=len(re.sub(r'\D','',value))<=15):raise ValueError('Enter a valid phone number.')
        return value


class CategoryRead(BaseModel):
    id:UUID
    name:str
class DonationOptions(BaseModel):
    enabled:bool
    mode:str='test'
    currency:str
    categories:list[CategoryRead]
class DonationInitialized(BaseModel):
    reference:str
    receipt_token:str
    authorization_url:str
class ReceiptRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    receipt_token:str=Field(pattern=r'^[0-9a-f]{64}$')
class DonationReceipt(BaseModel):
    reference:str
    amount:Decimal
    currency:str
    purpose:str
    status:str
    paid_at:datetime|None=None
class DonationRecord(DonationReceipt):
    id:UUID
    donor_name:str
    email:str
    phone:str
    note:str
    provider:str
    provider_reference:str
    created_at:datetime
