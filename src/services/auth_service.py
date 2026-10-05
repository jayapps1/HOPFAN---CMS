from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import (
    VerificationError,
    VerifyMismatchError,
)
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.config.database import SessionLocal
from src.models.user import User, UserStatus
from src.services.totp_service import TotpService


class AuthenticationError(Exception):
    pass


class PasswordRecoveryError(Exception):
    pass


class AuthService:
    MAX_FAILED_ATTEMPTS = 5
    LOCK_MINUTES = 15

    def __init__(self):
        self.password_hasher = PasswordHasher()
        self.totp = TotpService()

    def _load_user_with_roles(
        self,
        db,
        user_id,
    ):
        return db.scalar(
            select(User)
            .options(
                selectinload(User.roles)
            )
            .where(User.id == user_id)
        )

    def _detach_user(
        self,
        db,
        user,
    ):
        db.expunge(user)
        return user

    def _check_account_status(
        self,
        user,
    ):
        now = datetime.now(
            timezone.utc
        )

        if user.status == UserStatus.INACTIVE:
            raise AuthenticationError(
                "This account is inactive. "
                "Contact the administrator."
            )

        if user.status == UserStatus.SUSPENDED:
            raise AuthenticationError(
                "This account has been suspended."
            )

        if (
            user.status == UserStatus.LOCKED
            and user.locked_until
        ):
            locked_until = user.locked_until

            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(
                    tzinfo=timezone.utc
                )

            if locked_until > now:
                raise AuthenticationError(
                    "Your account is temporarily locked. "
                    "Please try again later."
                )

            user.status = UserStatus.ACTIVE
            user.locked_until = None
            user.failed_login_attempts = 0

    def _register_failed_attempt(
        self,
        user,
    ):
        now = datetime.now(
            timezone.utc
        )

        user.failed_login_attempts += 1

        if (
            user.failed_login_attempts
            >= self.MAX_FAILED_ATTEMPTS
        ):
            user.status = UserStatus.LOCKED

            user.locked_until = (
                now
                + timedelta(
                    minutes=self.LOCK_MINUTES
                )
            )

    # -------------------------------------------------
    # STEP 1 - EMAIL / PASSWORD
    # -------------------------------------------------

    def authenticate_password(
        self,
        email: str,
        password: str,
    ) -> User:
        email = email.strip().lower()

        if not email or not password:
            raise AuthenticationError(
                "Enter your email address and password."
            )

        with SessionLocal() as db:
            user = db.scalar(
                select(User)
                .options(
                    selectinload(User.roles)
                )
                .where(User.email == email)
            )

            if user is None:
                raise AuthenticationError(
                    "Invalid email address or password."
                )

            self._check_account_status(
                user
            )

            try:
                valid = (
                    self.password_hasher.verify(
                        user.password_hash,
                        password,
                    )
                )

            except (
                VerifyMismatchError,
                VerificationError,
            ):
                valid = False

            if not valid:
                self._register_failed_attempt(
                    user
                )

                db.commit()

                raise AuthenticationError(
                    "Invalid email address or password."
                )

            if (
                self.password_hasher
                .check_needs_rehash(
                    user.password_hash
                )
            ):
                user.password_hash = (
                    self.password_hasher.hash(
                        password
                    )
                )

            # Password sign-in is complete; authenticator sign-in is an alternative.
            user.failed_login_attempts = 0
            user.locked_until = None

            if user.status == UserStatus.LOCKED:
                user.status = UserStatus.ACTIVE

            db.commit()

            user = self._load_user_with_roles(
                db,
                user.id,
            )

            return self._detach_user(
                db,
                user,
            )

    # -------------------------------------------------
    # TOTP LOGIN
    # -------------------------------------------------

    def verify_totp(
        self,
        user_id,
        code: str,
    ) -> User:
        with SessionLocal() as db:
            user = self._load_user_with_roles(
                db,
                user_id,
            )

            if user is None:
                raise AuthenticationError(
                    "Unable to verify this login."
                )

            self._check_account_status(
                user
            )

            if (
                not user.totp_enabled
                or not user.totp_secret
            ):
                raise AuthenticationError(
                    "Authenticator verification "
                    "has not been configured."
                )

            valid = (
                self.totp.verify_encrypted(
                    user.totp_secret,
                    code,
                )
            )

            if not valid:
                self._register_failed_attempt(
                    user
                )

                db.commit()

                raise AuthenticationError(
                    "The verification code is incorrect "
                    "or has expired."
                )

            user.failed_login_attempts = 0
            user.locked_until = None
            user.status = UserStatus.ACTIVE

            user.last_login_at = datetime.now(
                timezone.utc
            )

            db.commit()

            user = self._load_user_with_roles(
                db,
                user.id,
            )

            return self._detach_user(
                db,
                user,
            )

    # -------------------------------------------------
    # FIRST-TIME TOTP SETUP
    # -------------------------------------------------

    def create_totp_enrollment(
        self,
        user_id,
    ):
        with SessionLocal() as db:
            user = db.get(
                User,
                user_id,
            )

            if user is None:
                raise AuthenticationError(
                    "Account not found."
                )

            secret = (
                self.totp.generate_secret()
            )

            uri = (
                self.totp.provisioning_uri(
                    secret,
                    user.email
                    or user.username,
                )
            )

            return secret, uri

    def confirm_totp_enrollment(
        self,
        user_id,
        secret: str,
        code: str,
    ) -> User:
        if not self.totp.verify_plain(
            secret,
            code,
        ):
            raise AuthenticationError(
                "The verification code is incorrect "
                "or has expired."
            )

        with SessionLocal() as db:
            user = self._load_user_with_roles(
                db,
                user_id,
            )

            if user is None:
                raise AuthenticationError(
                    "Account not found."
                )

            user.totp_secret = (
                self.totp.encrypt_secret(
                    secret
                )
            )

            user.totp_enabled = True

            user.totp_confirmed_at = (
                datetime.now(
                    timezone.utc
                )
            )

            user.last_login_at = (
                datetime.now(
                    timezone.utc
                )
            )

            user.failed_login_attempts = 0
            user.locked_until = None
            user.status = UserStatus.ACTIVE

            db.commit()

            user = self._load_user_with_roles(
                db,
                user.id,
            )

            return self._detach_user(
                db,
                user,
            )

    # -------------------------------------------------
    # ALTERNATIVE LOGIN - AUTHENTICATOR ONLY
    # -------------------------------------------------

    def authenticate_totp_only(
        self,
        email: str,
        code: str,
    ) -> User:
        email = email.strip().lower()
        code = code.strip()

        if not email:
            raise AuthenticationError(
                "Enter your email address."
            )

        if len(code) != 6 or not code.isdigit():
            raise AuthenticationError(
                "Enter a valid 6-digit authenticator code."
            )

        with SessionLocal() as db:
            user = db.scalar(
                select(User)
                .options(
                    selectinload(User.roles)
                )
                .where(User.email == email)
            )

            if user is None:
                raise AuthenticationError(
                    "Invalid email or authenticator code."
                )

            self._check_account_status(user)

            if (
                not user.totp_enabled
                or not user.totp_secret
            ):
                raise AuthenticationError(
                    "Authenticator login has not been "
                    "configured for this account."
                )

            valid = self.totp.verify_encrypted(
                user.totp_secret,
                code,
            )

            if not valid:
                self._register_failed_attempt(
                    user
                )

                db.commit()

                raise AuthenticationError(
                    "Invalid email or authenticator code."
                )

            user.failed_login_attempts = 0
            user.locked_until = None
            user.status = UserStatus.ACTIVE

            user.last_login_at = datetime.now(
                timezone.utc
            )

            db.commit()

            user = self._load_user_with_roles(
                db,
                user.id,
            )

            return self._detach_user(
                db,
                user,
            )

    # -------------------------------------------------
    # FORGOT PASSWORD USING AUTHENTICATOR
    # -------------------------------------------------

    def prepare_password_recovery(
        self,
        email: str,
    ):
        email = email.strip().lower()

        with SessionLocal() as db:
            user = db.scalar(
                select(User).where(
                    User.email == email
                )
            )

            if (
                user is None
                or not user.totp_enabled
                or not user.totp_secret
            ):
                raise PasswordRecoveryError(
                    "Self-service recovery is not "
                    "available for this account. "
                    "Please contact ICT."
                )

            return user.id

    def verify_recovery_totp(
        self,
        user_id,
        code: str,
    ):
        with SessionLocal() as db:
            user = db.get(
                User,
                user_id,
            )

            if (
                user is None
                or not user.totp_enabled
                or not user.totp_secret
            ):
                raise PasswordRecoveryError(
                    "Unable to verify this account."
                )

            if not self.totp.verify_encrypted(
                user.totp_secret,
                code,
            ):
                raise PasswordRecoveryError(
                    "The verification code is incorrect "
                    "or has expired."
                )

            return True

    def reset_password(
        self,
        user_id,
        new_password: str,
    ):
        self.validate_new_password(
            new_password
        )

        with SessionLocal() as db:
            user = db.get(
                User,
                user_id,
            )

            if user is None:
                raise PasswordRecoveryError(
                    "Account not found."
                )

            user.password_hash = (
                self.password_hasher.hash(
                    new_password
                )
            )

            user.failed_login_attempts = 0
            user.locked_until = None
            user.status = UserStatus.ACTIVE

            db.commit()

    @staticmethod
    def validate_new_password(
        password: str,
    ):
        if len(password) < 10:
            raise PasswordRecoveryError(
                "Password must contain at least "
                "10 characters."
            )

        if not any(
            char.isupper()
            for char in password
        ):
            raise PasswordRecoveryError(
                "Password must contain an uppercase letter."
            )

        if not any(
            char.islower()
            for char in password
        ):
            raise PasswordRecoveryError(
                "Password must contain a lowercase letter."
            )

        if not any(
            char.isdigit()
            for char in password
        ):
            raise PasswordRecoveryError(
                "Password must contain a number."
            )

        if not any(
            not char.isalnum()
            for char in password
        ):
            raise PasswordRecoveryError(
                "Password must contain a special character."
            )
