# Real_Estate_Parser

Instagram-only сервис парсинга недвижимости на `playwright`.

## Что умеет

- открывать Instagram-профиль или страницу источника
- при необходимости логиниться через `INSTAGRAM_USERNAME` и `INSTAGRAM_PASSWORD`
- использовать сохранённую сессию через `INSTAGRAM_SESSION_STATE_PATH`
- сохранять новую сессию после логина
- собирать ссылки на посты и reels
- открывать публикации и вытаскивать данные недвижимости из подписи
- отправлять результат в API или печатать JSON в stdout

## Структура

- `src/main.py` — точка входа
- `src/core/config.py` — настройки через env
- `src/clients/playwright.py` — Playwright client
- `src/parsers/instagram.py` — основная бизнес-логика парсинга Instagram
- `src/parsers/registry.py` — возврат активного parser
- `src/services/property.py` — orchestration и отправка в API
- `src/schemas/property.py` — схема объявления
- `docker-compose.yml` — автономный запуск parser-сервиса

## Как запускать отдельно

Из папки `RE_PARSER`:

```bash
cp .env.dev.example .env.dev
docker compose up --build
```

## Обязательные env

```env
MODE=dev
START_URL=https://www.instagram.com/your_account/
HEADLESS=true
BROWSER=chromium
TIMEOUT_MS=30000
MAX_ITEMS=20
INSTAGRAM_SCROLL_COUNT=3
INSTAGRAM_LOGIN_REQUIRED=false
INSTAGRAM_USERNAME=
INSTAGRAM_PASSWORD=
INSTAGRAM_SESSION_STATE_PATH=/app/.session/instagram.json
INSTAGRAM_SAVE_SESSION=false
API_BASE_URL=http://host.docker.internal:8000
```

## Сценарии

### Публичный аккаунт

```env
START_URL=https://www.instagram.com/your_account/
INSTAGRAM_LOGIN_REQUIRED=false
```

### Логин по учётке

```env
START_URL=https://www.instagram.com/your_account/
INSTAGRAM_LOGIN_REQUIRED=true
INSTAGRAM_USERNAME=your_login
INSTAGRAM_PASSWORD=your_password
INSTAGRAM_SAVE_SESSION=true
INSTAGRAM_SESSION_STATE_PATH=/app/.session/instagram.json
```

После первого успешного логина сессия сохранится в `RE_PARSER/.session/instagram.json`.

### Запуск с сохранённой сессией

```env
START_URL=https://www.instagram.com/your_account/
INSTAGRAM_LOGIN_REQUIRED=true
INSTAGRAM_SESSION_STATE_PATH=/app/.session/instagram.json
```

## Связь с API

Если `RE_API2` запущен отдельно через свой `docker compose` и публикует порт `8000`, то из parser-контейнера используй:

```env
API_BASE_URL=http://host.docker.internal:8000
```

Для этого в `docker-compose.yml` parser уже добавлен `extra_hosts` с `host-gateway`.

## Ограничения

Instagram может менять DOM, требовать логин, показывать дополнительные модалки и ограничивать automation. Поэтому сервис подготовлен к отдельному запуску, но для конкретного аккаунта-источника может понадобиться дополнительная настройка селекторов и логики извлечения текста.
