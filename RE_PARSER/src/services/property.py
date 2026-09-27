import json

from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.ai import AIClient
from src.clients.property_api import PropertyApiClient
from src.clients.telegram import TelegramNotifier
from src.parsers.registry import get_parser
from src.schemas.raw_post import RawPostAddSchema
from src.services.raw_post import RawPostService
from src.services.source import SourceService


class PropertyService:
    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session
        self.parser = get_parser()
        self.raw_post_service = RawPostService(db_session)
        self.source_service = SourceService(db_session)
        self.notifier = TelegramNotifier()
        self.ai_client = AIClient()
        self.property_api_client = PropertyApiClient()

    @staticmethod
    def _build_structured_text(extraction: dict, raw_caption: str | None) -> str:
        lines: list[str] = []

        price = extraction.get("price")
        currency_note = extraction.get("currency_note")
        if price is not None:
            price_line = f"💰 Цена: {price:g}"
            if currency_note:
                price_line += f" ({currency_note})"
            lines.append(price_line)
        elif currency_note:
            lines.append(f"💰 Цена: не указана ({currency_note})")

        lines.append(f"🏠 Тип: {extraction.get('property_type') or 'unknown'}")

        if extraction.get("rooms") is not None:
            lines.append(f"🛏 Комнат: {extraction['rooms']}")
        if extraction.get("area_sqm") is not None:
            lines.append(f"📐 Площадь: {extraction['area_sqm']:g} м²")

        location = extraction.get("city") or "unknown"
        if extraction.get("district"):
            location += f", {extraction['district']}"
        lines.append(f"📍 {location}")

        if extraction.get("contact"):
            lines.append(f"📞 Контакт: {extraction['contact']}")

        if extraction.get("ai_notes"):
            lines.append(f"\n🤖 {extraction['ai_notes']}")

        if raw_caption:
            lines.append(f"\nОригинал: {raw_caption}")

        return "\n".join(lines)

    @staticmethod
    def _build_description(extraction: dict, raw_caption: str | None) -> str:
        parts: list[str] = []
        if extraction.get("rooms") is not None:
            parts.append(f"Комнат: {extraction['rooms']}")
        if extraction.get("area_sqm") is not None:
            parts.append(f"Площадь: {extraction['area_sqm']} м²")
        if extraction.get("district"):
            parts.append(f"Район/адрес: {extraction['district']}")
        if extraction.get("currency_note"):
            parts.append(f"Цена: {extraction['currency_note']}")
        if extraction.get("ai_notes"):
            parts.append(f"Заметка ИИ: {extraction['ai_notes']}")
        if raw_caption:
            parts.append(f"Оригинал: {raw_caption}")
        return "\n".join(parts)

    async def _process_new_post(self, post: RawPostAddSchema) -> None:
        extraction = await self.ai_client.extract(
            caption=post.raw_caption,
            thumbnail_path=post.thumbnail_path,
        )

        if extraction is not None:
            await self.property_api_client.upsert_property(
                {
                    "title": extraction.get("title") or post.post_title or "Без названия",
                    "description": self._build_description(extraction, post.raw_caption),
                    "price": extraction.get("price"),
                    "url": str(post.post_url),
                    "source": post.source,
                    "city": extraction.get("city") or "unknown",
                    "property_type": extraction.get("property_type") or "unknown",
                    "external_id": post.external_id,
                    "contact": extraction.get("contact"),
                }
            )
            text = self._build_structured_text(extraction, post.raw_caption)
        else:
            # ИИ не настроен / упал / не уложился в таймаут — не теряем уведомление,
            # шлём как раньше, сырой подписью.
            text = post.raw_caption

        await self.notifier.notify_new_post(
            profile_username=post.profile_username,
            post_url=str(post.post_url),
            caption=text,
            media_paths=post.media_paths,
        )

    async def _collect_and_process(self, profile_username: str) -> int:
        """
        Обрабатывает посты по одному сразу по мере парсинга (сохранение в БД + ИИ + RE_API2 +
        Telegram), а не собирает все посты профиля в список и не обрабатывает их пачкой в конце.
        Иначе вызовы к RE_AI шли бы почти одновременно и упирались в rate limit бесплатного тира.
        """
        known_ids = await self.raw_post_service.get_known_external_ids(profile_username)
        # execute() выше молча открыл транзакцию (autobegin). Закрываем её ЗДЕСЬ, до начала
        # долгого Playwright-парсинга — иначе транзакция висит открытой минуты подряд, соединение
        # в пуле может протухнуть, и следующий DB-вызов падает с непонятной ошибкой SQLAlchemy.
        await self.db_session.commit()

        saved_count = 0
        async for post in self.parser.parse_iter(profile_username, known_external_ids=known_ids):
            await self.raw_post_service.add_raw_post(post)
            saved_count += 1
            await self._process_new_post(post)

        return saved_count

    async def parse_one(self, profile_username: str) -> int:
        """Разовый парсинг по запросу — используется эндпоинтом POST /parse."""
        return await self._collect_and_process(profile_username)

    async def process_sources(self) -> None:
        sources = await self.source_service.get_active_sources()
        await self.db_session.commit()  # см. комментарий в _collect_and_process
        if not sources:
            print("No active sources found.")
            return

        total_saved = 0
        for source in sources:
            print(f"Processing source: {source.profile_username}")
            try:
                saved_count = await self._collect_and_process(source.profile_username)
            except Exception as e:
                # Один упавший источник (login wall, бан, таймаут) не должен ронять весь цикл
                print(f"Source {source.profile_username} failed: {e}")
                try:
                    await self.db_session.rollback()
                except Exception as rollback_error:
                    print(f"Rollback also failed, session is likely dead: {rollback_error}")
                continue

            await self.source_service.update_last_checked_at(source.id)
            total_saved += saved_count
            print(f"Saved {saved_count} raw posts for source {source.profile_username}.")

        print(f"Saved {total_saved} raw posts in total.")

    async def dump_raw_posts(self) -> None:
        raw_posts = await self.raw_post_service.get_raw_posts()
        print(
            json.dumps(
                [
                    {
                        "id": item.id,
                        "source": item.source,
                        "profile_username": item.profile_username,
                        "external_id": item.external_id,
                        "post_url": item.post_url,
                        "ai_status": item.ai_status,
                    }
                    for item in raw_posts
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
