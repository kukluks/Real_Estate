FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
