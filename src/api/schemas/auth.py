import re
from typing import Literal

from pydantic import Field, SecretStr, field_validator

from src.api.schemas.common import ApiResponse


class PasswordLoginRequest(ApiResponse):
    email: str = Field(min_length=1, max_length=254)
    password: SecretStr = Field(min_length=1, max_length=4096)

    @field_validator("email")
    @classmethod
    def login_identifier(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Enter an email or username.")
        return value


class TotpLoginRequest(ApiResponse):
    email: str = Field(min_length=1, max_length=254)
    code: SecretStr = Field(min_length=6, max_length=6)

    _identifier = field_validator("email")(PasswordLoginRequest.login_identifier.__func__)

    @field_validator("code")
    @classmethod
    def six_digits(cls, value: SecretStr) -> SecretStr:
        if not re.fullmatch(r"[0-9]{6}", value.get_secret_value()):
            raise ValueError("Enter a six-digit authenticator code.")
        return value


class CsrfResponse(ApiResponse):
    csrf_token: str
    authenticated: bool


class LoginResponse(ApiResponse):
    status: Literal["authenticated"] = "authenticated"
    csrf_token: str


class LogoutResponse(ApiResponse):
    status: Literal["signed_out"] = "signed_out"
