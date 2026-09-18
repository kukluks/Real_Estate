# Real_Estate_API

API сервис для хранения объявлений недвижимости.

## Что умеет

- принимает объявления через `POST /properties/`
- возвращает список объявлений через `GET /properties/`
- автоматически накатывает Alembic миграции при старте контейнера
- поднимается отдельно через свой `docker-compose.yml`

## Как запускать

Из папки `RE_API2`:

```bash
cp .env.dev.example .env.dev
docker compose --env-file .env.dev up --build
```

## Как запускается контейнер

При старте `api` контейнера выполняется команда:

```sh
uv run alembic upgrade head && uv run python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

То есть миграции накатываются автоматически перед запуском API.

## Обязательные env

```env
MODE=dev
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=real_estate
POSTGRES_HOST=db
POSTGRES_PORT=5432
DB_PORT=5432
API_PORT=8000
```

## Эндпоинты

### Healthcheck

```http
GET /health
```

### Добавить или обновить объявление

```http
POST /properties/
Content-Type: application/json
```

### Получить объявления

```http
GET /properties/
```
