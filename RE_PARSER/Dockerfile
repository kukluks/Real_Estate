FROM mcr.microsoft.com/playwright/python:v1.55.0-jammy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir uv \
    && uv pip install --system .

CMD ["python", "src/main.py"]
