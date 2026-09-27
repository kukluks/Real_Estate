import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError

from src.core.config import settings
from src.db.base import Base
from src.db.session import async_session_maker, engine
from src.parsers.registry import get_parser
from src.schemas.raw_post import RawPostResponseSchema
from src.schemas.source import SourceAddSchema
from src.services.property import PropertyService
from src.services.source import SourceService

_monitor_task: asyncio.Task | None = None


async def _init_db_with_retries(max_attempts: int = 10, delay_seconds: float = 3.0) -> None:
    """
    Healthcheck в docker-compose иногда отвечает "Healthy" на пару секунд раньше, чем Postgres
    реально готов принимать соединения (особенно после нечистого выключения — идёт WAL-recovery).
    Раньше падение здесь роняло весь контейнер; теперь просто ждём и пробуем снова.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            return
        except OperationalError as e:
            print(f"DB not ready yet (attempt {attempt}/{max_attempts}): {e}")
            if attempt == max_attempts:
                raise
            await asyncio.sleep(delay_seconds)


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
    # Раньше это было внутри main()/asyncio.run(), которые CMD "uvicorn src.main:app" никогда не вызывал.
    # lifespan гарантированно отрабатывает при старте, независимо от способа запуска uvicorn.
    await _init_db_with_retries()

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


class ParseRequest(BaseModel):
    profile_username: str


async def get_db():
    async with async_session_maker() as session:
        yield session


@app.post("/sources")
async def add_source(source: SourceRequest, db=Depends(get_db)):
    parser = get_parser()
    try:
        exists = await parser.profile_exists(source.profile_username)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to check Instagram profile: {e}") from e

    if not exists:
        raise HTTPException(status_code=404, detail=f"Instagram profile '{source.profile_username}' not found.")

    service = SourceService(db)
    try:
        result = await service.add_source(SourceAddSchema(profile_username=source.profile_username))
        return {"status": "success", "source_id": result.id, "message": f"Source {source.profile_username} added"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/parse")
async def parse_profile(request: ParseRequest, db=Depends(get_db)):
    service = PropertyService(db)
    try:
        saved_count = await service.parse_one(request.profile_username)
        return {"status": "success", "posts_count": saved_count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/posts", response_model=list[RawPostResponseSchema])
async def get_posts(db=Depends(get_db)):
    service = PropertyService(db)
    return await service.raw_post_service.get_raw_posts()


@app.get("/health")
async def health_check():
    return {"status": "ok"}
