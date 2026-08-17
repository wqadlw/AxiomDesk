"""统一异常与处理器。

所有业务异常继承 AppError；注册后由 FastAPI 统一转换为带 request_id 的
结构化 JSON 响应，便于前端与日志系统消费。
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..logging_setup import get_logger

logger = get_logger("api.errors")


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, status_code: int | None = None, code: str | None = None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class UpstreamError(AppError):
    status_code = 502
    code = "upstream_error"


def _handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "request failed: rid=%s status=%s code=%s msg=%s",
        getattr(request.state, "request_id", "-"),
        exc.status_code,
        exc.code,
        exc.message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "code": exc.code, "request_id": getattr(request.state, "request_id", "-")},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handler)  # type: ignore[arg-type]

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logger.exception("unhandled exception: rid=%s", getattr(request.state, "request_id", "-"))
        return JSONResponse(
            status_code=500,
            content={
                "error": "内部错误，请稍后重试",
                "code": "internal_error",
                "request_id": getattr(request.state, "request_id", "-"),
            },
        )
