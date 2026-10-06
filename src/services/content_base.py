from contextlib import contextmanager
from datetime import datetime,timezone
from uuid import UUID
from sqlalchemy.exc import SQLAlchemyError
from src.config.database import SessionLocal
from src.services.authorization_service import AuthorizationService,AuthorizationDenied
from src.services.operation_errors import OperationConflict,OperationNotFound
from src.models.content import ContentAudit

class ContentError(Exception):pass
class ContentDenied(ContentError,AuthorizationDenied):pass
class ContentConflict(ContentError,OperationConflict):pass
class ContentMissing(ContentError,OperationNotFound):pass
def now():return datetime.now(timezone.utc)
def ident(value):return UUID(str(value))
def check_version(row,expected):
    if expected is None or row.updated_at!=expected:raise ContentConflict('This record changed. Refresh before saving.')
class ContentBase:
    def __init__(self,user_id=None,session_factory=SessionLocal):self.user_id,self.session_factory=user_id,session_factory
    @contextmanager
    def _db(self,permission=None):
        with self.session_factory() as db:
            try:
                access=AuthorizationService.load(db,self.user_id)
                if permission:access.require_permission(permission)
                yield db,access
            except AuthorizationDenied:raise
            except SQLAlchemyError as error:
                db.rollback();raise ContentError('The content operation could not be completed.') from error
    @staticmethod
    def audit(db,access,kind,entity_id,action,**details):
        db.add(ContentAudit(entity_kind=kind,entity_id=entity_id,action=action,
            actor_user_id=access.user_id if access else None,details=details))
