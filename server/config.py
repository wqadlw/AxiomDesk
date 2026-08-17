"""集中配置 · 全部可通过环境变量 UZI_* 覆盖（见 .env.example）。

企业级约定：
  - 12 因子配置（环境变量优先，文件兜底 .env）
  - 密钥/端口/数据源均可外部注入，便于容器化与多环境部署
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="UZI_",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── 服务 ──
    app_name: str = "AxiomDesk 公理级投研终端"
    host: str = "127.0.0.1"
    port: int = 8137
    api_v1_prefix: str = "/api/v1"
    docs_url: str = "/docs"
    cors_origins: str = "*"  # 逗号分隔，生产环境请显式限定

    # ── 数据层 ──
    # auto   = 真实多源优先（依次尝试 akshare→efinance→tushare→baostock），全部不可用则回退 demo（默认）
    # demo   = 确定性合成/内置个股（纯离线，不联网）
    # akshare = 强制指定 akshare 实时行情，失败自动回退 demo
    data_source: str = "auto"
    data_dir: str = ".data"  # 历史/任务持久化目录（SQLite）
    cache_ttl: int = 3600  # 行情缓存秒数
    cache_dir: str = ".cache"  # 磁盘缓存目录（相对 cwd）

    # ── 可观测性 ──
    log_level: str = "INFO"  # DEBUG/INFO/WARNING/ERROR
    log_json: bool = False  # True = 结构化 JSON 日志（便于接入 Loki/ELK）
    log_file: str = ""  # 非空则同时写文件（旋转）

    # ── 安全 ──
    max_request_body: int = 1_048_576  # 预留：请求体上限（字节）


settings = Settings()
