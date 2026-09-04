# Real_Estate_Parser

Сервис парсинга недвижимости на `playwright` с поддержкой нескольких сайтов.

## Структура

- `src/main.py` — точка входа для запуска парсинга
- `src/core/config.py` — настройки приложения
- `src/clients/playwright.py` — управление браузером Playwright
- `src/parsers/base.py` — базовый интерфейс парсера
- `src/parsers/registry.py` — реестр парсеров
- `src/parsers/example.py` — тестовый parser
- `src/parsers/lalafo.py` — parser для Lalafo
- `src/services/property.py` — orchestration-слой
- `src/schemas/property.py` — схема объявления и enum источников

## Источники

Сейчас поддержаны:

- `example`
- `lalafo`

Новые сайты удобно добавлять отдельными файлами в `src/parsers/` и регистрировать в `src/parsers/registry.py`.

## Запуск

```bash
uv run python src/main.py
```

## Пример `.env.dev`

```env
MODE=dev
PARSER_NAME=lalafo
START_URL=https://lalafo.kg/kyrgyzstan/nedvizhimost
HEADLESS=true
BROWSER=chromium
TIMEOUT_MS=30000
MAX_ITEMS=20
API_BASE_URL=http://localhost:8000
```

## Установка браузеров Playwright

```bash
uv run playwright install
```

## Примечание

У Lalafo, как и у других маркетплейсов, вёрстка может меняться. Текущий `src/parsers/lalafo.py` — это хорошая стартовая база, но селекторы, возможно, придётся подправить под реальную страницу выдачи.
