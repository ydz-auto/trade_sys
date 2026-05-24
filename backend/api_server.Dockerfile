FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || pip install --no-cache-dir --ignore-installed -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["python", "api_server.py"]
