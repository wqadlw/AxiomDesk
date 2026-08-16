"""UZI 投研终端 · FastAPI 应用工厂。

运行：
    python -m server.app                 # 开发/本地
    uvicorn server.app:app --host 0.0.0.0 --port 8137
前端：挂载 server/../web 为静态资源（/, /app.js, /style.css ...）
"""

from __future__ import annotations

from pathlib import Path

try:  # 作为包导入（推荐：python -m server.app / tests）
    from .api.errors import register_exception_handlers
    from .api.middleware import add_middleware
    from .api.routes import router, router_v1
    from .config import settings
    from .logging_setup import get_logger, setup_logging
except ImportError:  # 作为脚本直接运行（python server/app.py）
    import sys
    from pathlib import Path as _P

    # 把 server/ 的【父目录】加入 sys.path，使本模块以 `server` 包的形式被导入，
    # 这样子模块里的相对导入（from .config / from ..engine 等）都能正确解析。
    sys.path.insert(0, str(_P(__file__).parent.parent))
    from server.api.errors import register_exception_handlers  # type: ignore
    from server.api.middleware import add_middleware  # type: ignore
    from server.api.routes import router, router_v1  # type: ignore
    from server.config import settings  # type: ignore
    from server.logging_setup import get_logger, setup_logging  # type: ignore

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

WEB_DIR = Path(__file__).parent.parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    log = get_logger("app")
    log.info("UZI 投研终端启动 | host=%s port=%s data_source=%s", settings.host, settings.port, settings.data_source)
    yield
    log.info("UZI 投研终端关闭")


def create_app() -> FastAPI:
    setup_logging()
    get_logger("app")

    app = FastAPI(
        title=settings.app_name,
        version="2.0.0",
        description=(
            "UZI-Skill 企业级落地：66 位投资大佬评审团 × 20 维框架 × DCF/Comps/LBO 估值 "
            "× 8 信号杀猪盘检测。所有分析为规则引擎离线确定性计算，仅供研究参考，非投资建议。"
        ),
        docs_url=settings.docs_url or None,
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    register_exception_handlers(app)
    add_middleware(app)

    # 双前缀：/api（当前契约）与 /api/v1（版本化）
    app.include_router(router, prefix="/api")
    app.include_router(router_v1, prefix="/api/v1")

    # 静态资源（web 前端）；html=True 使 "/" 返回 index.html
    if WEB_DIR.exists():
        app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")

    return app


app = create_app()


def run() -> None:
    """控制台入口（``pip install`` 后可用 ``uzi-terminal`` 启动）。"""
    import uvicorn

    uvicorn.run(
        "server.app:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
