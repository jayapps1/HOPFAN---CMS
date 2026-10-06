"""Read-only online readiness checks using the existing synchronous session."""
from sqlalchemy import text
from sqlalchemy.orm import Session


class DatabaseUnavailable(Exception):
    """The database cannot serve this request; raw causes remain private."""


class DatabaseAccessUnsafe(Exception):
    """API database sessions must not have PostgreSQL superuser privileges."""


def check_api_database_access(db: Session) -> None:
    # Check both the authenticated login and any effective SET ROLE identity.
    # Fail closed if the PostgreSQL role information is unavailable.
    allowed = db.execute(text(
        "SELECT NOT COALESCE(bool_or(rolsuper), true) "
        "FROM pg_roles WHERE rolname IN (session_user, current_user)"
    )).scalar_one()
    if allowed is not True:
        raise DatabaseAccessUnsafe()


def check_database_readiness(db: Session) -> None:
    try:
        if db.execute(text("SELECT 1")).scalar_one() != 1:
            raise DatabaseUnavailable()
    except Exception:
        raise DatabaseUnavailable() from None
