from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

import http_messages

_log = logging.getLogger(__name__)

_NORMALIZED: dict[int, str] = {
    403: http_messages.HTTP_403,
    404: http_messages.HTTP_404,
    429: http_messages.HTTP_429,
    500: http_messages.HTTP_500,
    503: http_messages.HTTP_503,
}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    def http_exception_handler(
        _request: Request, exc: HTTPException
    ) -> JSONResponse:
        if exc.status_code in _NORMALIZED:
            body: Any = _NORMALIZED[exc.status_code]
        else:
            body = exc.detail
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": body},
            headers=exc.headers,
        )

    @app.exception_handler(SQLAlchemyError)
    def sqlalchemy_error_handler(
        _request: Request, exc: SQLAlchemyError
    ) -> JSONResponse:
        if isinstance(exc, IntegrityError):
            _log.info("Database integrity error", exc_info=exc)
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": http_messages.HTTP_400},
            )
        _log.exception("Database error")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": http_messages.HTTP_503},
        )

    @app.exception_handler(Exception)
    def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        _log.exception("Unexpected error in request")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": http_messages.HTTP_500},
        )
