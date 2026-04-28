from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

_log = logging.getLogger(__name__)

_NORMALIZED: dict[int, str] = {
    403: "You don't have permission to access this resource.",
    404: "The requested resource was not found.",
    429: "Too many requests. Please slow down and try again later.",
    500: "An internal error occurred. Please try again later.",
    503: "The service is temporarily unavailable. Please try again later.",
    400: "The request could not be completed. Please check your information and try again.",
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
                content={"detail": _NORMALIZED[400]},
            )
        _log.error("Database error", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": _NORMALIZED[503]},
        )

    @app.exception_handler(Exception)
    def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        _log.exception("Unexpected error in request")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": _NORMALIZED[500]},
        )
