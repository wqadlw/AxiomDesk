# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 规范，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)（当前 API 版本见 `server/api/routes.py:API_VERSION`）。

## [2.0.0] — 2026-08-16

### 工程化与最佳实践
- 引入 `pyproject.toml` 作为依赖与工具（ruff / black / isort / mypy / pytest）的唯一事实来源；`requirements.txt` 仅保留给 Docker / 生产镜像并与之同步。
- 新增 `.pre-commit-config.yaml`（ruff + ruff-format + mypy 门禁）。
- CI（`ci.yml`）新增 `quality` 任务：lint / format / type 检查 + 多版本 Python（3.10/3.11/3.12）测试矩阵 + 前端 `node --check`。
- `server.app:app` 改为工厂模式，`run()` 作为 `uzi-terminal` 控制台入口。

### 数据诚实化（核心修复）
- 修复「空心分析」：实时源（腾讯/新浪）仅返回行情字段，旧版对未命中内置近似表的标的跑在 0 值基本面上。
- `derive_features` 现由实时 `PE/PB` 严格推导 `EPS = 现价/PE`、`BVPS = 现价/PB`、`ROE ≈ PB/PE`（TTM 恒等式）。
- 新增 `data_quality` 溯源块（`live` / `estimated` / `demo`）与 `data_note` / `data_disclaimer`，前端报告头部展示对应徽标与免责声明。
- 任意有实时行情的 A 股现在都能得到**有意义且诚实**的分析。

### 可靠性
- 修复 `config_store` ↔ `providers.factory` 的循环导入，应用现在可干净启动（不再依赖残留进程）。
- `api/routes._analyze` 将引擎异常统一转为 4xx，杜绝未捕获 500。

## [1.0.0] — 2026-08-16

### 初始开源发布
- FastAPI 版本化 API（`/api` + `/api/v1`）、结构化日志与 Request-ID。
- 66 位投资大师评审团 + 三模型估值（DCF/Comps/LBO）+ 8 信号杀猪盘检测 + 多空大分歧辩论。
- 零依赖直连腾讯/新浪实时行情，可配置多源故障转移，离线 `demo` 兜底。
- AI 研判层（DeepSeek 可选，无 Key 自动降级模板）。
- 彭博风原生 JS/CSS 前端（红涨绿跌，9 个 Tab）。
- Docker / Compose / Makefile / CI 与完整文档（ARCHITECTURE / METHODOLOGY / API）。
