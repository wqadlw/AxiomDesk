"""AxiomDesk · 服务端包。

企业级分层结构：
  server/
    config.py         配置（pydantic-settings，环境变量 UZI_*）
    logging_setup.py  结构化日志（请求级 request-id）
    app.py            FastAPI 应用工厂 create_app()
    engine/           分析引擎（估值 / 66 评委 / 20 维 / 陷阱 / 编排）
    providers/        数据层（多源 provider + 缓存 + 回退）
    api/              HTTP 层（路由 / schema / 异常 / 中间件）
"""
