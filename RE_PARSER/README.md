# Real_Estate_Parser

Instagram-only сервис парсинга недвижимости на `playwright`.

## Как теперь работает parser

Parser работает по варианту `A`: через таблицу источников `sources`.

Поток такой:

1. ты добавляешь Instagram-профиль в `sources`
2. потом запускаешь parser
3. parser проходит по всем активным источникам
4. собирает `raw_posts`
5. сохраняет их в свою БД

## Команды внутри parser

При запуске контейнера parser спрашивает действие:

```text
Choose action: [1] add source, [2] run parser once, [3] show raw posts, [4] monitor (loop)
```

### 1. Добавить источник

Выбираешь:

```text
1
```

Потом вводишь username профиля:

```text
Enter Instagram profile: kvartira_osh98
```

### 2. Запустить parser (один раз)

Выбираешь:

```text
2
```

Тогда parser пройдёт по всем активным источникам из БД и соберёт новые посты (инкрементально, используя `last_checked_at`).

### 3. Посмотреть сохранённые raw posts

Выбираешь:

```text
3
```

### 4. Режим мониторинга (бесконечный цикл)

Выбираешь:

```text
4
```

Parser будет каждые `MONITOR_INTERVAL_SECONDS` (по умолчанию 300с) обходить активные источники и сохранять новые посты. Остановка — `Ctrl+C`.

## Инкрементальный сбор

- Парсер использует `source.last_checked_at` как точку отсчёта (`since`).
- При скролле ленты останавливается, когда встречает пост старше `since`.
- Дедупликация по `external_id` (unique constraint в БД) — повторные запуски безопасны.
- Жёсткий лимит безопасности: `SAFETY_MAX_ITEMS` (по умолчанию 100) на один проход.

## Что хранится в БД parser

### Таблица `sources`
- `source_type`
- `profile_username`
- `profile_url`
- `is_active`
- `notes`
- `last_checked_at`
- `created_at`

### Таблица `raw_posts`
- `source`
- `profile_username`
- `external_id`
- `post_url`
- `raw_caption`
- `media_urls`
- `thumbnail_url`
- `published_at`
- `fetched_at`
- `ai_status`

## Запуск

```bash
docker compose --env-file .env.dev build
docker compose --env-file .env.dev run --rm re_parser
```

## База parser

У parser свой Postgres. По умолчанию наружу он публикуется на:

```text
localhost:5434
```
