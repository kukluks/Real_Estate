FROM mcr.microsoft.com/playwright/python:v1.62.0-jammy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir uv \
    && uv pip install --system .

CMD ["python", "src/main.py"]
