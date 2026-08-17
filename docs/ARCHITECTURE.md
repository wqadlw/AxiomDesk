# 架构说明 (Architecture)

本文档描述 AxiomDesk 的分层架构、请求生命周期、数据契约与部署方式。

## 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│  web/  (原生 JS / CSS 前端，无构建步骤，彭博风终端)            │
│   index.html · app.js · style.css                             │
└───────────────────────────┬─────────────────────────────────┘
                              │  REST  /api  +  /api/v1
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  server/app.py  FastAPI 应用工厂 (create_app + lifespan)      │
│   ├─ api/middleware.py    Request-ID / CORS / 结构化日志       │
│   ├─ api/routes.py        版本化路由（分析/任务/历史/对比/配置）│
│   ├─ api/errors.py        统一异常 → 标准错误体               │
│   ├─ api/schemas.py       Pydantic 请求/响应模型             │
│   ├─ engine/             确定性强引擎                          │
│   │    data_provider → investors → valuation → engine         │
│   │    narrative (AI 研判层) · personas (声纹)                │
│   ├─ providers/          数据源抽象 + Failover + 缓存          │
│   │    base · factory · cache · registry · http_base          │
│   │    tencent/sina/eastmoney · optional(akshare/efinance/…)  │
│   │    demo (确定性兜底)                                      │
│   ├─ llm/                DeepSeek / 模板 研判（零依赖）        │
│   ├─ jobs.py             SQLite 异步任务 + 历史               │
│   ├─ config_store.py     配置持久化 (config.json, 可热更新)   │
│   └─ config.py           pydantic-settings (UZI_ 前缀)        │
└─────────────────────────────────────────────────────────────┘
```

## 请求生命周期（以 `/api/analyze` 为例）

1. 中间件注入 `X-Request-ID`，记录结构化日志。
2. `routes._analyze` 校验参数（`AnalyzeParams`：`ticker` 非空、`depth∈{lite,medium,deep}`、`boost∈0..4`）。
3. `engine.analyze(ticker, keyword_boost, depth, use_ai)`：
   - `data_provider.get_profile` → 经 `factory` 选择的数据源链（真实源失败自动降级 `demo`）。
   - `derive_features` → 20 维原始特征；**并由实时 `PE/PB` 严格推导 `EPS = 现价/PE`、`BVPS = 现价/PB`、`ROE ≈ PB/PE`**，附 `data_quality` 溯源块（见下）。
   - 评分（66 评委 `fields` 白名单加权）→ `overall_score` / `verdict`。
   - 估值：`valuation` 三模型（DCF / Comps / LBO），**以 Comps 为锚** 综合公允价。
   - 陷阱检测：8 信号 + 加权。
   - 多空辩论：`great_divide` 取最强多/空 + 同组代表兜底。
   - `narrative.generate_narrative` → AI 研判（DeepSeek 或模板回退），挂 `result["ai"]`。
4. 同步分析与异步任务均落库（`jobs.get_store().record_sync` / `run`）。
5. 统一响应体返回；异常经 `errors.py` 转为 4xx/5xx 标准错误。

## 数据契约：Provider 抽象

所有数据源实现 `server/providers/base.py:DataProvider`：

```python
class DataProvider:
    name: str
    def is_available(self) -> bool: ...          # 仅判断“能否尝试”，HTTP 源恒 True（不做联网探测）
    def get_profile(self, ticker: str) -> dict: ...   # 失败抛 ProviderError
    def get_peers(self, ticker, profile, n=5) -> list[dict]: ...
    def ping(self) -> float: ...                  # 延迟探测（秒）
```

故障转移链（`factory.FallbackProvider`）在调用时捕获 `ProviderError` 并降级到下一节点，
末节点恒为 `DemoDataProvider`，保证**永不返回半截数据 / 永不崩溃**。

## 数据溯源与诚实化设计

实时源（腾讯/新浪）通常只返回 `现价 / PE / PB / 市值 / 动量 / 波动率`，**不含完整财报**。
若直接把空基本面喂给 66 维评分与估值，会产出「看起来专业、实则跑在 0 值上」的空洞结论。

为此 `derive_features` 在缺失财报时，用可由实时字段严格推导的财务恒等式补齐锚点：

| 推导量 | 公式 | 来源 |
|--------|------|------|
| `EPS` 每股收益 | `现价 / PE` | TTM 恒等式 |
| `BVPS` 每股净资产 | `现价 / PB` | 账面价值定义 |
| `ROE` 净资产收益率 | `(P/PE)/(P/PB) = PB/PE` | 杜邦恒等式近似 |

同时产出 `data_quality` 溯源块，分三档透明标注：

- `live`：行情实时 **且** 财报完整（如命中内置近似基本面兜底）——结论可参考。
- `estimated`：行情实时，但财报缺失 → 基本面由 PE/PB 推导，结论为粗略参考（报告附醒目免责声明）。
- `demo`：离线合成数据，仅供体验（报告附合成数据声明）。

报告头（`data_note`）与免责声明（`data_disclaimer`）据此生成，前端在报告顶部展示对应徽标。
该设计让**任意有实时行情的 A 股都能得到有意义且诚实的分析**，是「专业 / 不误导」的核心保障。

## 配置与热更新

- `config_store` 持久化到 `config.json`（路径：`UZI_CONFIG` 环境变量或项目根）。
- 修改配置（`PUT /api/config`）后调用 `reload_provider()` + `reload_llm()` 立即重建链路。
- `UZI_DATA_SOURCE` 环境变量可强制覆盖 `data_source`（容器注入 / 测试离线关键）。

## 部署

| 方式 | 命令 | 说明 |
|------|------|------|
| 本地 | `python -m uvicorn server.app:app --port 8137` | 开发 / 演示 |
| 脚本 | `./start.sh` / `start.bat` | 自动探测端口、后台启动、开浏览器 |
| Docker | `docker compose up --build` | 非 root、healthcheck、数据卷持久化 |
| 生产 | 反向代理 (nginx) + uvicorn workers | 建议 `UZI_LOG_JSON=true` 接入日志系统 |

## 目录结构

```
uzi-platform/
├─ server/            # 后端（FastAPI + 引擎 + 数据源 + LLM）
├─ web/               # 前端（原生 JS/CSS，无构建）
├─ tests/             # pytest 套件（离线 demo 模式）
├─ docs/              # ARCHITECTURE / METHODOLOGY / API
├─ pyproject.toml     # 依赖与工程化工具（ruff/black/isort/mypy/pytest）的唯一事实来源
├─ requirements.txt   # 仅 Docker / 生产镜像使用，内容与 pyproject 同步
├─ Dockerfile / docker-compose.yml / Makefile
├─ .github/workflows/ci.yml
├─ .pre-commit-config.yaml
├─ LICENSE / NOTICE / README.md / CONTRIBUTING.md ...
└─ config.json        # 运行时生成，已 gitignore
```
