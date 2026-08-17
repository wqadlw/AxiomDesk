# AxiomDesk · 轻量生产镜像
# 依赖与工具配置统一收敛于 pyproject.toml（唯一事实来源）。
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AXIOM_HOST=0.0.0.0 \
    AXIOM_PORT=8137 \
    AXIOM_DATA_SOURCE=auto

WORKDIR /app

# 先拷贝构建元数据与源码（利用层缓存）
COPY pyproject.toml README.md ./
COPY server/ ./server/
COPY web/ ./web/

# 从 pyproject.toml 安装运行时依赖 + 本项目（server 包）
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# 非 root 运行
RUN useradd -m -u 10001 axiom && chown -R axiom:axiom /app
USER axiom

EXPOSE 8137

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8137/api/health').status==200 else 1)"

# server 被安装进 site-packages，WEB_DIR 会自动回退到 /app/web
CMD ["python", "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8137"]
