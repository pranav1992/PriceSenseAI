import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .exceptions import AppException
from .middleware import REQUEST_ID_HEADER

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    request_id = get_request_id(request)
    logger.warning(
        "Application error: %s",
        exc.code,
        extra={"request_id": request_id, "error_code": exc.code},
    )

    return error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        request_id=request_id,
        details=exc.details,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = get_request_id(request)
    details = [
        {
            "field": ".".join(str(part) for part in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]

    return error_response(
        status_code=422,
        code="VALIDATION_ERROR",
        message="Request validation failed.",
        request_id=request_id,
        details=details,
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    request_id = get_request_id(request)
    message = exc.detail if isinstance(exc.detail, str) else "HTTP error."
    details = None if isinstance(exc.detail, str) else exc.detail

    return error_response(
        status_code=exc.status_code,
        code="HTTP_ERROR",
        message=message,
        request_id=request_id,
        details=details,
        headers=exc.headers,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = get_request_id(request)
    logger.exception(
        "Unhandled exception",
        extra={"request_id": request_id},
    )

    return error_response(
        status_code=500,
        code="INTERNAL_SERVER_ERROR",
        message="Internal server error.",
        request_id=request_id,
    )


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request_id: str,
    details: Any | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
        }
    }

    if details is not None:
        content["error"]["details"] = details

    headers = dict(headers or {})
    if request_id:
        headers[REQUEST_ID_HEADER] = request_id

    return JSONResponse(status_code=status_code, content=content, headers=headers)


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")
