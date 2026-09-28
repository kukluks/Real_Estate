import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.core.config import settings
from src.db.session import async_session_maker
from src.parsers.registry import get_parser
from src.schemas.raw_post import RawPostResponseSchema
from src.schemas.source import SourceAddSchema
from src.services.property import PropertyService
from src.services.source import SourceService

_monitor_task: asyncio.Task | None = None


def _normalize_username(raw: str) -> str:
    """Instagram-логины регистронезависимы; без нормализации @Foo и foo стали бы двумя
    разными источниками и скрапились бы дважды."""
    return raw.strip().lstrip("@").strip("/").lower()


async def _monitor_loop() -> None:
    """
    Фоновый цикл внутри самого API-процесса. Источники читаются из БД заново на каждом
    круге (через process_sources -> get_active_sources), поэтому источник, добавленный через
    POST /sources прямо сейчас, подхватится сам на следующем круге — рестарт контейнера не нужен.
    """
    while True:
        async with async_session_maker() as session:
            try:
                await PropertyService(session).process_sources()
            except Exception as e:
                print(f"Monitor cycle failed: {e}")
        await asyncio.sleep(settings.MONITOR_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Схема БД накатывается через Alembic до старта uvicorn (см. Dockerfile / docker-compose).
    global _monitor_task
    _monitor_task = asyncio.create_task(_monitor_loop())
    try:
        yield
    finally:
        if _monitor_task:
            _monitor_task.cancel()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SourceRequest(BaseModel):
    profile_username: str
    added_by_chat_id: str | None = None


class ParseRequest(BaseModel):
    profile_username: str


async def get_db():
    async with async_session_maker() as session:
        yield session


@app.post("/sources")
async def add_source(source: SourceRequest, db=Depends(get_db)):
    username = _normalize_username(source.profile_username)
    if not username:
        raise HTTPException(status_code=400, detail="Instagram profile username cannot be empty.")

    service = SourceService(db)

    # Если профиль уже кто-то добавил, он уже проверен — не гоняем браузер ради повторной проверки.
    if not await service.profile_is_tracked(username):
        parser = get_parser()
        try:
            exists = await parser.profile_exists(username)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Failed to check Instagram profile: {e}") from e

        if not exists:
            raise HTTPException(status_code=404, detail=f"Instagram profile '{username}' not found.")

    try:
        result = await service.add_source(
            SourceAddSchema(
                profile_username=username,
                added_by_chat_id=source.added_by_chat_id,
            )
        )
        return {"status": "success", "source_id": result.id, "message": f"Source {username} added"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/sources")
async def list_sources(owner_chat_id: str, db=Depends(get_db)):
    """Источники одного пользователя — то, что он видит по команде /my_sources."""
    sources = await SourceService(db).list_by_owner(owner_chat_id)
    return [{"id": s.id, "profile_username": s.profile_username} for s in sources]


@app.delete("/sources")
async def delete_sources(owner_chat_id: str, profile_username: str | None = None, db=Depends(get_db)):
    """Удаляет источник владельца; без profile_username — все его источники (при /revoke)."""
    username = _normalize_username(profile_username) if profile_username else None
    deleted = await SourceService(db).delete_sources(owner_chat_id, username)
    if username and deleted == 0:
        raise HTTPException(status_code=404, detail=f"Source '{username}' not found for this user.")
    return {"status": "success", "deleted": deleted}


@app.post("/parse")
async def parse_profile(request: ParseRequest, db=Depends(get_db)):
    service = PropertyService(db)
    try:
        saved_count = await service.parse_one(_normalize_username(request.profile_username))
        return {"status": "success", "posts_count": saved_count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/posts", response_model=list[RawPostResponseSchema])
async def get_posts(owner_chat_id: str | None = None, db=Depends(get_db)):
    """
    С owner_chat_id — только посты профилей этого пользователя (без отброшенных ИИ как «не
    недвижимость»). Без параметра — вообще все посты, для отладки. Это фильтр, а не
    авторизация: любой, кто знает chat_id, может его передать.
    """
    service = PropertyService(db)
    if owner_chat_id:
        return await service.raw_post_service.get_raw_posts_for_owner(owner_chat_id)
    return await service.raw_post_service.get_raw_posts()


@app.get("/health")
async def health_check():
    return {"status": "ok"}
