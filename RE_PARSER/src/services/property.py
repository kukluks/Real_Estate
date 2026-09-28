import asyncio
import json

from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.ai import AIClient
from src.clients.property_api import PropertyApiClient
from src.clients.telegram import TelegramNotifier
from src.core.config import settings
from src.db.repository import AI_STATUS_PROCESSED, AI_STATUS_SKIPPED, AI_STATUS_UNAVAILABLE
from src.db.session import async_session_maker
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

    async def _process_new_post(
        self,
        post: RawPostAddSchema,
        *,
        owner_chat_ids: list[str | None],
    ) -> None:
        """
        ИИ и RE_API2 — один раз на пост (это не зависит от того, сколько человек следят за
        профилем), а вот уведомление уходит КАЖДОМУ владельцу источника отдельно.
        """
        extraction = await self.ai_client.extract(
            caption=post.raw_caption,
            thumbnail_path=post.thumbnail_path,
        )

        if extraction is not None:
            if not extraction.get("is_real_estate", True):
                snippet = " ".join((post.raw_caption or "").split())[:60]
                print(f"Skip non-real-estate post {post.external_id} (@{post.profile_username}): {snippet!r}")
                await self.raw_post_service.set_ai_status(post.external_id, AI_STATUS_SKIPPED)
                return

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
            await self.raw_post_service.set_ai_status(post.external_id, AI_STATUS_PROCESSED)
        else:
            text = post.raw_caption
            await self.raw_post_service.set_ai_status(post.external_id, AI_STATUS_UNAVAILABLE)

        for chat_id in owner_chat_ids:
            await self.notifier.notify_new_post(
                profile_username=post.profile_username,
                post_url=str(post.post_url),
                caption=text,
                media_paths=post.media_paths,
                target_chat_id=chat_id,
            )

    async def _collect_and_process(
        self,
        profile_username: str,
        *,
        owner_chat_ids: list[str | None] | None = None,
    ) -> int:
        """
        Обрабатывает посты по одному сразу по мере парсинга (сохранение в БД + ИИ + RE_API2 +
        Telegram), а не собирает все посты профиля в список и не обрабатывает их пачкой в конце.
        """
        owners = owner_chat_ids if owner_chat_ids else [None]

        known_ids = await self.raw_post_service.get_known_external_ids(profile_username)
        # Закрываем транзакцию до долгого Playwright — иначе соединение в пуле может протухнуть.
        await self.db_session.commit()

        saved_count = 0
        async for post in self.parser.parse_iter(profile_username, known_external_ids=known_ids):
            await self.raw_post_service.add_raw_post(post)
            saved_count += 1
            await self._process_new_post(post, owner_chat_ids=owners)

        return saved_count

    async def parse_one(self, profile_username: str) -> int:
        """Разовый парсинг по запросу — используется эндпоинтом POST /parse."""
        return await self._collect_and_process(profile_username)

    @staticmethod
    async def _process_profile_job(
        profile_username: str,
        owners: list[str | None],
        source_ids: list[int],
        semaphore: asyncio.Semaphore,
    ) -> int:
        """
        Один профиль в отдельной DB-сессии под семафором.
        Своя сессия обязательна: AsyncSession нельзя безопасно делить между concurrent-задачами.
        """
        async with semaphore:
            print(
                f"Processing profile: {profile_username} "
                f"(owners={owners}, concurrency_slot acquired)"
            )
            async with async_session_maker() as session:
                service = PropertyService(session)
                try:
                    saved_count = await service._collect_and_process(
                        profile_username,
                        owner_chat_ids=owners,
                    )
                    for source_id in source_ids:
                        await service.source_service.update_last_checked_at(source_id)
                    print(f"Saved {saved_count} raw posts for profile {profile_username}.")
                    return saved_count
                except Exception as e:
                    print(f"Profile {profile_username} failed: {e}")
                    try:
                        await session.rollback()
                    except Exception as rollback_error:
                        print(f"Rollback also failed, session is likely dead: {rollback_error}")
                    return 0

    async def process_sources(self) -> None:
        sources = await self.source_service.get_active_sources()
        await self.db_session.commit()
        if not sources:
            print("No active sources found.")
            return

        # Группируем по профилю: один scrape — уведомления всем владельцам.
        owners_by_profile: dict[str, list[str | None]] = {}
        source_ids_by_profile: dict[str, list[int]] = {}
        for source in sources:
            owners = owners_by_profile.setdefault(source.profile_username, [])
            if source.added_by_chat_id not in owners:
                owners.append(source.added_by_chat_id)
            source_ids_by_profile.setdefault(source.profile_username, []).append(source.id)

        concurrency = max(1, settings.SCRAPE_CONCURRENCY)
        semaphore = asyncio.Semaphore(concurrency)
        print(
            f"Starting scrape cycle: {len(owners_by_profile)} profiles, "
            f"concurrency={concurrency}"
        )

        tasks = [
            self._process_profile_job(
                profile_username,
                owners,
                source_ids_by_profile[profile_username],
                semaphore,
            )
            for profile_username, owners in owners_by_profile.items()
        ]
        results = await asyncio.gather(*tasks)
        total_saved = sum(results)
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
