FROM python:3.12-slim

WORKDIR /app

COPY services/llm_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "services.llm_service.main"]
