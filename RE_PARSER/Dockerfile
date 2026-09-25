FROM mcr.microsoft.com/playwright/python:v1.62.0-jammy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir \
    uvicorn==0.27.0 \
    fastapi==0.109.0 \
    playwright==1.62.0 \
    httpx==0.27.0 \
    sqlalchemy==2.0.25 \
    asyncpg==0.29.0 \
    pydantic==2.5.3 \
    pydantic-settings==2.1.0

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
