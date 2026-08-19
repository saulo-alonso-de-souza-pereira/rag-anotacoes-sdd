from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


@dataclass(slots=True)
class ApiError(Exception):
    status_code: int
    code: str
    message: str
    field_errors: list[dict[str, str]] | None = None


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        candidate = request.headers.get("x-request-id")
        try:
            request_id = str(UUID(candidate)) if candidate else str(uuid4())
        except ValueError:
            request_id = str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["Cache-Control"] = "no-store"
        return response


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid4()))


def _envelope(
    request: Request,
    *,
    code: str,
    message: str,
    field_errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": _request_id(request),
    }
    if field_errors:
        detail["field_errors"] = field_errors
    return {"error": detail}


def install_error_handlers(app: FastAPI) -> None:
    app.add_middleware(RequestContextMiddleware)

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, error: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content=_envelope(
                request,
                code=error.code,
                message=error.message,
                field_errors=error.field_errors,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        fields = [
            {
                "field": ".".join(str(part) for part in item["loc"] if part != "body"),
                "message": item["msg"],
            }
            for item in error.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_envelope(
                request,
                code="validation_error",
                message="A solicitação contém dados inválidos.",
                field_errors=fields,
            ),
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, _error: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=_envelope(
                request,
                code="internal_error",
                message="Não foi possível concluir a solicitação.",
            ),
        )
