# UZI Terminal · 常用命令
PY ?= python
PORT ?= 8137

.PHONY: help install dev test run docker docker-up docker-down clean

help:
	@echo "Targets:"
	@echo "  install    安装 Python 依赖"
	@echo "  dev        安装依赖 + 测试依赖"
	@echo "  test       运行 pytest（离线 demo 模式）"
	@echo "  run        启动开发服务 (127.0.0.1:$(PORT))"
	@echo "  docker-up   docker compose 构建并启动"
	@echo "  docker-down停止并移除容器"
	@echo "  clean      清理运行时残留"

install:
	$(PY) -m pip install -r requirements.txt

dev: install
	$(PY) -m pip install pytest httpx

test:
	$(PY) -m pytest -q

run:
	$(PY) -m uvicorn server.app:app --host 127.0.0.1 --port $(PORT)

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

clean:
	rm -rf .data .cache .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
