# 贡献指南 (Contributing)

感谢你考虑为 **UZI Terminal** 做出贡献！本文档说明如何本地开发、提交 Issue 与 PR。

## 行为准则

参与本项目的所有社区成员均需遵守 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

## 提 Issue

- 搜索是否已有相同或相关的 Issue。
- Bug 请附：复现步骤、期望行为、实际行为、环境变量（`UZI_DATA_SOURCE` 等）、日志片段。
- 功能建议请说明使用场景与价值。

## 开发环境

```bash
# 1. Fork 并克隆你的副本
git clone https://github.com/<you>/uzi-terminal.git
cd uzi-terminal

# 2. 创建虚拟环境（推荐）
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install pytest httpx                            # 测试依赖

# 3. 本地运行
python -m uvicorn server.app:app --port 8137

# 4. 运行测试（默认离线 demo 模式，不污染仓库）
pytest -q
```

## 代码规范

- **Python**：遵循 PEP 8；类型注解尽量完整；新增逻辑补 pytest 用例。
- **前端**：原生 JS / CSS，无构建步骤；保持红涨绿跌（中国习惯）；避免引入重依赖。
- **数据源**：新增实时源请继承 `server/providers/base.py:DataProvider`，在 `registry.py` 注册，并在「数据源配置」页面自动可见。
- **保密**：切勿提交 `config.json`、`.env`、密钥或真实账户信息（已被 `.gitignore` 排除）。

## 提交 PR

1. 从 `main` 切出特性分支：`git checkout -b feat/your-feature`。
2. 保持提交原子、信息清晰（如 `feat: 新增网易财经数据源`）。
3. 确保 `pytest -q` 通过、前端无控制台报错。
4. 在 PR 描述中说明：改动内容、动机、测试方式、是否影响默认行为（尤其数据源 / API）。

## 评审

维护者会审查代码质量、测试覆盖与文档完整性。请耐心回应评审意见。

---

谢谢你的贡献！🎉
