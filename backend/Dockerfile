FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ./app ./app
# Cloud Run injects the PORT env var (default 8080) and the container must
# listen on it. Shell form so ${PORT} is expanded at runtime; falls back to
# 8000 for local `docker run` without PORT set.
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
