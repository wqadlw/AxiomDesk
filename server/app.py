"""AxiomDesk 公理级投研终端 · FastAPI 应用工厂。

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

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


def _resolve_web_dir() -> Path:
    """定位前端 web 目录。

    兼容多种部署形态：
      - 开发态：源码 server/ 与 web/ 同级（Path(__file__).parent.parent / "web"）
      - 安装态：server 被装进 site-packages（WEB_DIR 落在包外），需回退到工作目录 /app/web
      - 容器态：WORKDIR=/app 且 web 拷贝到 /app/web
      - 环境变量 UZI_WEB_DIR 可强制指定
    """
    candidates = []
    if env_web := os.environ.get("UZI_WEB_DIR"):
        candidates.append(Path(env_web))
    candidates.append(Path(__file__).parent.parent / "web")  # 开发态
    candidates.append(Path.cwd() / "web")  # 当前工作目录
    candidates.append(Path("/app/web"))  # 容器默认
    for c in candidates:
        if c.exists():
            return c
    return candidates[1]  # 回退到开发态路径（即便不存在也给出确定值）


WEB_DIR = _resolve_web_dir()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log = get_logger("app")
    log.info(
        "AxiomDesk 公理级投研终端启动 | host=%s port=%s data_source=%s",
        settings.host,
        settings.port,
        settings.data_source,
    )
    yield
    log.info("AxiomDesk 公理级投研终端关闭")


def create_app() -> FastAPI:
    setup_logging()
    get_logger("app")

    app = FastAPI(
        title=settings.app_name,
        version="3.0.1",
        description=(
            "AxiomDesk 公理级投研终端：市场情绪层 × 策略指标层 × 执行闭环 × 智能增强 四层研判，"
            "66 位投资大佬评审团 × 20 维框架 × DCF/Comps/LBO 估值 × 游资确定性双轨评分 × 跨会话记忆。"
            "分析为规则引擎确定性计算 + 可选 AI 研判，仅供研究参考，非投资建议。"
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
    """控制台入口（``pip install`` 后可用 ``axiomdesk`` 启动）。"""
    import uvicorn

    uvicorn.run(
        "server.app:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
