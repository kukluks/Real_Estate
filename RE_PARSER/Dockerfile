FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir uv \
    && uv pip install --system . \
    && python -m playwright install chromium

CMD ["python", "src/main.py"]
