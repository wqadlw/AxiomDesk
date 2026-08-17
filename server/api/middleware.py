"""HTTP 中间件：请求 ID 透传 + 访问日志 + CORS。"""

from __future__ import annotations

import time
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import settings
from ..logging_setup import get_logger, request_id_ctx

logger = get_logger("api.middleware")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:12]
        token = request_id_ctx.set(rid)
        request.state.request_id = rid
        start = time.time()
        try:
            response = await call_next(request)
        except Exception:
            request_id_ctx.reset(token)
            raise
        duration_ms = int((time.time() - start) * 1000)
        response.headers["X-Request-ID"] = rid
        logger.info(
            "%s %s -> %d (%dms) rid=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            rid,
        )
        request_id_ctx.reset(token)
        return response


def _cors_origins() -> list[str]:
    if settings.cors_origins in ("*", "", None):
        return ["*"]
    return [o.strip() for o in settings.cors_origins.split(",") if o.strip()]


def add_middleware(app: FastAPI) -> None:
    # 安全：CORS 凭证（cookie/授权头）与通配源互斥——带凭证时不能用 "*"，
    # 否则浏览器会拒绝。仅当显式指定源时才允许凭证。
    origins = _cors_origins()
    allow_credentials = origins != ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)
