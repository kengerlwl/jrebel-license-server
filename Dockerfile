# JRebel & JetBrains License Server
FROM python:3.11-slim

LABEL maintainer="xiaoyu-ai"
LABEL description="JRebel & JetBrains License Server"

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=58080

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 58080

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:58080/api/status || exit 1

# 启动命令
CMD ["gunicorn", "--bind", "0.0.0.0:58080", "--workers", "2", "--threads", "4", "app:app"]