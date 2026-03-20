FROM python:3.13-slim

WORKDIR /app

# 安装依赖（先复制 requirements 利用 Docker 层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令（生产环境不开 --reload，worker 数量按 CPU 核心数调整）
CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--access-log"]
