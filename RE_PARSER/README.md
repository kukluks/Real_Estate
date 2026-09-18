# Real_Estate_Parser

Instagram-only сервис парсинга недвижимости на `playwright`.

## Что умеет

- при запуске спрашивает имя Instagram-профиля в консоли
- открывает указанный профиль через `Playwright`
- при необходимости логинится через `INSTAGRAM_USERNAME` и `INSTAGRAM_PASSWORD`
- использует или сохраняет сессию через `INSTAGRAM_SESSION_STATE_PATH`
- собирает ссылки на посты и reels
- открывает публикации и кладёт посты в API/БД
- если API не указан — печатает JSON в stdout

## Как запускать

Из папки `RE_PARSER`:

```bash
cp .env.dev.example .env.dev
docker compose build

docker compose run --rm re_parser
```

Для интерактивного режима лучше использовать именно `docker compose run --rm re_parser`, а не `docker compose up`, потому что ввод через `stdin` у `run` работает стабильнее.

После старта контейнер спросит:

```text
Enter Instagram profile:
```

Ты вводишь, например:

```text
agency_bishkek
```

И parser пойдёт в:

```text
https://www.instagram.com/agency_bishkek/
```

## Обязательные env

```env
MODE=dev
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

## Что попадёт в БД

Сейчас parser просто складывает сырые посты в БД через API. Для каждого поста он пытается сохранить:

- `title`
- `description`
- `price`
- `url`
- `source`
- `city`
- `property_type`
- `external_id`
- `contact`

Потом на этот слой можно будет отдельно навесить ИИ-анализ.

## Логин-сценарий

Если нужен логин:

```env
INSTAGRAM_LOGIN_REQUIRED=true
INSTAGRAM_USERNAME=your_login
INSTAGRAM_PASSWORD=your_password
INSTAGRAM_SAVE_SESSION=true
INSTAGRAM_SESSION_STATE_PATH=/app/.session/instagram.json
```

После первого успешного логина сессия сохранится в `RE_PARSER/.session/instagram.json`.

## Связь с API

Если `RE_API2` запущен отдельно через свой `docker compose` и публикует порт `8000`, укажи:

```env
API_BASE_URL=http://host.docker.internal:8000
```

## Что увидишь в логах

При успешном запуске будут сообщения примерно такого вида:

```text
Enter Instagram profile: agency_bishkek
Opening Instagram profile: agency_bishkek
Found 12 posts/reels on profile agency_bishkek.
Parsed 8 posts from profile agency_bishkek.
Sent 8 posts to API.
```

Если ничего не нашлось:

```text
No posts were parsed.
```
