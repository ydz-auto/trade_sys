FROM python:3.12-slim

WORKDIR /app

COPY services/data_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "services.data_service.main_kafka"]
