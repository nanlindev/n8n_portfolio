FROM python:3.12-slim

WORKDIR /app

# 安装必要的系统依赖（如果需要）
RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

# 修改这里：使用 opentelemetry-instrument 包装 uvicorn
CMD ["opentelemetry-instrument", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]