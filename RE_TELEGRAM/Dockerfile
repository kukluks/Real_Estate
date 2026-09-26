FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir \
    uvicorn==0.27.0 \
    fastapi==0.109.0 \
    httpx==0.27.0 \
    pydantic==2.5.3 \
    pydantic-settings==2.1.0 \
    python-multipart==0.0.9

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002"]
