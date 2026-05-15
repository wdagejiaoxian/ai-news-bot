# ========================================
# AI News Bot Backend Dockerfile
# ========================================

FROM python:3.11-slim AS builder

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
# 国内 PyPI 镜像（如遇网络问题可换其他镜像）
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

# 安装构建依赖
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件（利用 Docker 缓存）
COPY requirements.txt .

# 安装 Python 依赖（单独层级，便于缓存）
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ ./app/

# 复制 docker-compose.rsshub.yml（RSSHub Manager 在容器内自动启动 RSSHub 时需要）
COPY docker-compose.rsshub.yml ./

# 创建存储目录
RUN mkdir -p /app/storage

# 最终运行镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 从 builder 复制已安装的依赖
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY --from=builder /app /app

# 复制环境变量文件模板（实际部署时会被 docker-compose 的 env_file 覆盖）
COPY .env.example /app/.env

# 安装健康检查所需工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]