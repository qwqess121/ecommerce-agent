# 电商客服智能体 — 容器镜像
# 用途：Cloudflare Containers / Hugging Face Spaces (Docker) / 任意 Docker 平台
# 说明：默认无 LLM_API_KEY 时自动进入 Mock 演示模式，离线即可回答，无需任何密钥。
FROM python:3.13-slim

# 系统依赖：chromadb / langchain 在 slim 镜像上需要 libgomp 与编译工具链
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8080

WORKDIR /app

# 先装依赖（利用层缓存，代码变更不需重装）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再复制全部代码
COPY . .

# 确保运行时可写目录存在（Chroma 向量库、上传目录）
RUN mkdir -p /app/vectorstore /app/kb/uploads

EXPOSE 8080

# 监听 $PORT（Cloudflare/HF 会传入），默认 8080
CMD ["sh", "-c", "uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
