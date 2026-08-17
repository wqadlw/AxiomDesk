# UZI Terminal · 开发 / 质量 / 部署 一体化命令
# 依赖与工具配置统一收敛于 pyproject.toml（唯一事实来源）。
PY    ?= python
PORT  ?= 8137

.PHONY: help install dev lint format lint-fix type security test run docker-up docker-down clean

help:
	@echo "Targets:"
	@echo "  install     安装运行时依赖 (pip install -e .)"
	@echo "  dev         安装运行时 + 开发/质量门禁依赖 (pip install -e \".[dev]\")"
	@echo "  lint        ruff 静态检查"
	@echo "  format      ruff 格式化检查"
	@echo "  lint-fix    自动修复 lint / 格式化"
	@echo "  type        mypy 类型检查"
	@echo "  security    bandit 安全扫描 (依据 .bandit)"
	@echo "  test        运行 pytest（离线 demo 模式 + 覆盖率）"
	@echo "  run         启动开发服务 (127.0.0.1:$(PORT))"
	@echo "  docker-up   docker compose 构建并启动"
	@echo "  docker-down 停止并移除容器"
	@echo "  clean       清理运行时 / 缓存残留"

install:
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e .

dev: install
	$(PY) -m pip install -e ".[dev]"

lint:
	$(PY) -m ruff check server tests

format:
	$(PY) -m ruff format --check server tests

lint-fix:
	$(PY) -m ruff check --fix server tests
	$(PY) -m ruff format server tests

type:
	$(PY) -m mypy server

security:
	$(PY) -m bandit -r server -c .bandit

test:
	$(PY) -m pytest --cov=server --cov-report=term-missing

run:
	$(PY) -m uvicorn server.app:app --host 127.0.0.1 --port $(PORT) --reload

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

clean:
	rm -rf .data .cache .pytest_cache .ruff_cache .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
