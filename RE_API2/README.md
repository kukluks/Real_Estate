# Real_Estate_API

API сервис для хранения объявлений недвижимости.

## Что умеет

- принимает объявления через `POST /properties/`
- возвращает список объявлений через `GET /properties/`
- автоматически создаёт таблицы в базе при старте
- поднимается отдельно через свой `docker-compose.yml`

## Как запускать

Из папки `RE_API2`:

```bash
cp .env.dev.example .env.dev
docker compose up --build
```

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

Пример тела:

```json
{
  "title": "3-комнатная квартира в Бишкеке",
  "description": "Отличная квартира рядом с центром",
  "price": 125000,
  "url": "https://www.instagram.com/p/ABC123/",
  "source": "instagram",
  "city": "бишкек",
  "property_type": "apartment",
  "external_id": "ABC123",
  "contact": "+996555123456"
}
```

### Получить объявления

```http
GET /properties/
```
