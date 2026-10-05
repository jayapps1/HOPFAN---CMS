"""Password or authenticator sign-in with lockout, proof-bound recovery and audit."""
from datetime import datetime, timedelta, timezone
import secrets
import time
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from src.config.database import SessionLocal
from src.models import User, UserStatus, Role, SecurityAuditLog


class AuthenticationError(Exception):
    pass


class PasswordRecoveryError(Exception):
    pass


class AuthService:
    MAX_FAILED_ATTEMPTS = 5
    LOCK_MINUTES = 15
    PROOF_SECONDS = 600

    def __init__(self, session_factory=SessionLocal):
        from src.services.totp_service import TotpService
        self.session_factory = session_factory
        self.password_hasher = PasswordHasher()
        self.totp = TotpService()
        self._proofs = {}
        self._recovery_proofs = {}
        self._pending_enrollments = {}
        # Verification of an unknown login also performs Argon2 work.
        self._dummy_hash = self.password_hasher.hash(secrets.token_urlsafe(24))

    @staticmethod
    def _event(db, user, action, **values):
        import json
        db.add(SecurityAuditLog(target_user_id=user.id if user else None,
            action=action, new_values=json.dumps(values, sort_keys=True)))

    @staticmethod
    def _load_user_with_roles(db, user_id):
        return db.scalar(select(User).where(User.id == user_id).options(selectinload(User.roles)))

    @staticmethod
    def _check_account_status(user):
        now=datetime.now(timezone.utc)
        if user.status in (UserStatus.INACTIVE,UserStatus.SUSPENDED):
            raise AuthenticationError('This account is inactive or suspended. Contact the administrator.')
        if user.status == UserStatus.LOCKED:
            if user.locked_until is None or user.locked_until > now:
                raise AuthenticationError('Your account is locked. Contact the administrator or try again after the temporary lock expires.')
            user.status=UserStatus.ACTIVE
            user.locked_until=None
            user.failed_login_attempts=0

    def _failed(self, db, user, method):
        user.failed_login_attempts+=1
        self._event(db,user,'LOGIN_FAILED',method=method)
        if user.failed_login_attempts>=self.MAX_FAILED_ATTEMPTS:
            user.status=UserStatus.LOCKED
            user.locked_until=datetime.now(timezone.utc)+timedelta(minutes=self.LOCK_MINUTES)
            user.auth_revision+=1
            self._event(db,user,'ACCOUNT_LOCKED',temporary=True)
        db.commit()

    def _issue_proof(self,user,purpose):
        token=secrets.token_urlsafe(32)
        self._proofs={k:v for k,v in self._proofs.items() if v[3]>time.monotonic()}
        self._proofs[token]=(user.id,user.auth_revision,purpose,time.monotonic()+self.PROOF_SECONDS)
        return token

    def _require_proof(self,user,token,purposes):
        proof=self._proofs.get(token)
        if not proof or proof[0]!=user.id or proof[1]!=user.auth_revision or proof[2] not in purposes or proof[3]<=time.monotonic():
            raise AuthenticationError('Verify your account again before continuing.')
        self._check_account_status(user)

    def _signed_in(self,db,user,method):
        user.failed_login_attempts=0
        user.locked_until=None
        user.status=UserStatus.ACTIVE
        user.last_login_at=datetime.now(timezone.utc)
        self._event(db,user,'LOGIN_VERIFIED' if user.require_password_change else 'LOGIN_SUCCESS',method=method)
        db.commit()
        user=self._load_user_with_roles(db,user.id)
        token=self._issue_proof(user,'sign_in')
        db.expunge(user)
        user._authentication_ticket=token
        user._auth_service=self
        return user

    @staticmethod
    def _lookup(db,login):
        value=login.strip().lower()
        return db.scalar(select(User).where(or_(func.lower(User.email)==value,func.lower(User.username)==value))
            .options(selectinload(User.roles)).with_for_update())

    def authenticate_password(self,email,password):
        if not email.strip() or not password:
            raise AuthenticationError('Enter your email or username and password.')
        with self.session_factory() as db:
            user=self._lookup(db,email)
            if user:
                try:
                    self._check_account_status(user)
                except AuthenticationError:
                    self._event(db,user,'LOGIN_REJECTED',method='password')
                    db.commit()
                    raise
            try:
                valid=self.password_hasher.verify(user.password_hash if user else self._dummy_hash,password)
            except VerificationError:
                valid=False
            if not user or not valid:
                if user:
                    self._failed(db,user,'password')
                else:
                    self._event(db,None,'LOGIN_FAILED',method='password')
                    db.commit()
                raise AuthenticationError('Invalid email, username or password.')
            if self.password_hasher.check_needs_rehash(user.password_hash):
                user.password_hash=self.password_hasher.hash(password)
            return self._signed_in(db,user,'password')

    def authenticate_totp_only(self,email,code):
        if not email.strip() or len(code.strip())!=6 or not code.strip().isdigit():
            raise AuthenticationError('Enter your email or username and a valid six-digit authenticator code.')
        with self.session_factory() as db:
            user=self._lookup(db,email)
            if not user:
                self._event(db,None,'LOGIN_FAILED',method='authenticator')
                db.commit()
                raise AuthenticationError('Invalid email, username or authenticator code.')
            try:
                self._check_account_status(user)
            except AuthenticationError:
                self._event(db,user,'LOGIN_REJECTED',method='authenticator')
                db.commit()
                raise
            if not user.totp_enabled or not user.totp_secret:
                self._event(db,user,'LOGIN_REJECTED',method='authenticator',not_configured=True)
                db.commit()
                raise AuthenticationError('Authenticator login is not configured. Sign in with your password to enroll it.')
            if not self.totp.verify_encrypted(user.totp_secret,code.strip()):
                self._failed(db,user,'authenticator')
                raise AuthenticationError('Invalid email, username or authenticator code.')
            return self._signed_in(db,user,'authenticator')

    def verify_totp(self,user_id,code):
        # Compatibility path still verifies the authenticator itself.
        with self.session_factory() as db:
            user=self._load_user_with_roles(db,user_id)
            if not user:
                raise AuthenticationError('Account not found.')
            login=user.email or user.username
        return self.authenticate_totp_only(login,code)

    def change_initial_password(self,user_id,new_password,confirm_password,ticket):
        self.validate_new_password(new_password)
        if new_password!=confirm_password:
            raise PasswordRecoveryError('The passwords do not match.')
        with self.session_factory() as db:
            user=db.scalar(select(User).where(User.id==user_id).with_for_update())
            if not user:
                raise AuthenticationError('Account not found.')
            self._require_proof(user,ticket,{'sign_in'})
            if not user.require_password_change:
                raise AuthenticationError('A temporary password change is no longer pending.')
            try:
                unchanged=self.password_hasher.verify(user.password_hash,new_password)
            except VerificationError:
                unchanged=False
            if unchanged:
                raise PasswordRecoveryError('Choose a new password different from the temporary password.')
            user.password_hash=self.password_hasher.hash(new_password)
            user.require_password_change=False
            user.auth_revision+=1
            self._proofs.pop(ticket,None)
            self._event(db,user,'PASSWORD_CHANGED')
            return self._signed_in(db,user,'password_change')

    def create_totp_enrollment(self,user_id,ticket=None):
        with self.session_factory() as db:
            user=db.get(User,user_id)
            if not user:
                raise AuthenticationError('Account not found.')
            self._require_proof(user,ticket,{'sign_in'})
            if user.require_password_change:
                raise AuthenticationError('Change your temporary password first.')
            if user.totp_enabled:
                raise AuthenticationError('An authenticator is already configured. Request a controlled reset before replacing it.')
            secret=self.totp.generate_secret()
            self._pending_enrollments[ticket]=(secret,user.auth_revision)
            return secret,self.totp.provisioning_uri(secret,user.email or user.username)

    def confirm_totp_enrollment(self,user_id,secret,code,ticket=None):
        with self.session_factory() as db:
            user=db.scalar(select(User).where(User.id==user_id).with_for_update())
            if not user:
                raise AuthenticationError('Account not found.')
            self._require_proof(user,ticket,{'sign_in'})
            pending=self._pending_enrollments.get(ticket)
            if user.require_password_change or user.totp_enabled or not pending or pending!=(secret,user.auth_revision):
                raise AuthenticationError('Start a new authenticator enrollment.')
            if not self.totp.verify_plain(secret,code):
                self._failed(db,user,'enrollment')
                raise AuthenticationError('The verification code is incorrect or has expired.')
            user.totp_secret=self.totp.encrypt_secret(secret)
            user.totp_enabled=True
            user.totp_confirmed_at=datetime.now(timezone.utc)
            self._pending_enrollments.pop(ticket,None)
            self._event(db,user,'TOTP_ENROLLED',totp_enabled=True)
            return self._signed_in(db,user,'enrollment')

    def cancel_totp_enrollment(self,user_id,ticket):
        proof=self._proofs.get(ticket)
        if proof and proof[0]==user_id:
            self._pending_enrollments.pop(ticket,None)
            self._proofs.pop(ticket,None)

    def prepare_password_recovery(self,email):
        with self.session_factory() as db:
            user=self._lookup(db,email)
            if not user or not user.totp_enabled or not user.totp_secret:
                raise PasswordRecoveryError('Self-service recovery is not available for this account. Please contact ICT.')
            try:
                self._check_account_status(user)
            except AuthenticationError as exc:
                raise PasswordRecoveryError(str(exc)) from exc
            return user.id

    def verify_recovery_totp(self,user_id,code):
        with self.session_factory() as db:
            user=db.scalar(select(User).where(User.id==user_id).with_for_update())
            if not user or not user.totp_enabled or not user.totp_secret:
                raise PasswordRecoveryError('Unable to verify this account.')
            try:
                self._check_account_status(user)
            except AuthenticationError as exc:
                raise PasswordRecoveryError(str(exc)) from exc
            if not self.totp.verify_encrypted(user.totp_secret,code):
                self._failed(db,user,'recovery')
                raise PasswordRecoveryError('The verification code is incorrect or has expired.')
            token=self._issue_proof(user,'recovery')
            self._recovery_proofs[user.id]=token
            self._event(db,user,'RECOVERY_VERIFIED')
            db.commit()
            return True

    def reset_password(self,user_id,new_password):
        self.validate_new_password(new_password)
        with self.session_factory() as db:
            user=db.scalar(select(User).where(User.id==user_id).with_for_update())
            if not user:
                raise PasswordRecoveryError('Account not found.')
            token=self._recovery_proofs.get(user.id)
            try:
                self._require_proof(user,token,{'recovery'})
            except AuthenticationError as exc:
                raise PasswordRecoveryError(str(exc)) from exc
            user.password_hash=self.password_hasher.hash(new_password)
            user.require_password_change=False
            user.failed_login_attempts=0
            user.locked_until=None
            user.auth_revision+=1
            self._proofs.pop(token,None)
            self._recovery_proofs.pop(user.id,None)
            self._event(db,user,'PASSWORD_RECOVERED')
            db.commit()

    def session_valid(self,user_id,auth_revision):
        with self.session_factory() as db:
            user=db.get(User,user_id)
            return bool(user and user.status==UserStatus.ACTIVE and not user.require_password_change and user.auth_revision==auth_revision)

    def record_session_end(self,user_id,action='LOGOUT'):
        if action not in {'LOGOUT','IDLE_EXPIRED','SESSION_REVOKED'}:
            raise ValueError('Invalid session event.')
        with self.session_factory() as db:
            user=db.get(User,user_id)
            if user:
                self._event(db,user,action)
                db.commit()

    @staticmethod
    def validate_new_password(password):
        if len(password)<10:
            raise PasswordRecoveryError('Password must contain at least 10 characters.')
        for valid,message in ((any(c.isupper() for c in password),'an uppercase letter'),
            (any(c.islower() for c in password),'a lowercase letter'),
            (any(c.isdigit() for c in password),'a number'),
            (any(not c.isalnum() for c in password),'a special character')):
            if not valid:
                raise PasswordRecoveryError('Password must contain '+message+'.')
