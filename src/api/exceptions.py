from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from src.api.schemas.common import ErrorDetail, ErrorResponse
from src.services.api_readiness_service import DatabaseAccessUnsafe, DatabaseUnavailable
from src.services.web_security import WebSecurityError
from src.api.security.session import clear_session_cookie
from sqlalchemy.exc import SQLAlchemyError


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ErrorResponse(error=ErrorDetail(code=code, message=message)).model_dump(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(WebSecurityError)
    def web_security_error(request: Request, exc: WebSecurityError) -> JSONResponse:
        response = error_response(exc.status, exc.code, exc.message)
        if exc.clear_cookie:
            clear_session_cookie(response, request.app.state.settings)
        if exc.retry_after is not None:
            response.headers["Retry-After"] = str(exc.retry_after)
        return response

    @app.exception_handler(SQLAlchemyError)
    def database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        return error_response(503, "DATABASE_UNAVAILABLE", "The database is temporarily unavailable.")

    @app.exception_handler(HTTPException)
    def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        errors = {
            400: ("INVALID_REQUEST", "The request could not be processed."),
            401: ("AUTHENTICATION_REQUIRED", "Authentication is required."),
            403: ("ACCESS_DENIED", "Access to this resource is denied."),
            404: ("RESOURCE_NOT_FOUND", "The requested resource was not found."),
            405: ("METHOD_NOT_ALLOWED", "This request method is not allowed."),
        }
        code, message = errors.get(exc.status_code, ("REQUEST_FAILED", "The request could not be completed."))
        response = error_response(exc.status_code, code, message)
        # Keep only protocol headers needed by future authentication/route logic.
        for name, value in (exc.headers or {}).items():
            if name.lower() in {"allow", "www-authenticate", "retry-after"}:
                response.headers[name] = value
        return response

    @app.exception_handler(RequestValidationError)
    def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic's default details can echo passwords, tokens and raw inputs.
        return error_response(422, "VALIDATION_ERROR", "The request contains invalid data.")

    @app.exception_handler(DatabaseUnavailable)
    def database_unavailable(request: Request, exc: DatabaseUnavailable) -> JSONResponse:
        return error_response(503, "DATABASE_UNAVAILABLE", "The database is temporarily unavailable.")

    @app.exception_handler(DatabaseAccessUnsafe)
    def database_access_unsafe(request: Request, exc: DatabaseAccessUnsafe) -> JSONResponse:
        return error_response(503, "DATABASE_ACCESS_UNSAFE", "The database access configuration is not suitable for the API.")
