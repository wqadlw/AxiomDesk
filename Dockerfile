# UZI Terminal · 轻量生产镜像
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UZI_HOST=0.0.0.0 \
    UZI_PORT=8137

WORKDIR /app

# 依赖先装（利用层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 源码
COPY server/ ./server/
COPY web/ ./web/
COPY tests/ ./tests/

# 非 root 运行
RUN useradd -m -u 10001 uzi && chown -R uzi:uzi /app
USER uzi

EXPOSE 8137

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8137/api/health').status==200 else 1)"

CMD ["python", "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8137"]
