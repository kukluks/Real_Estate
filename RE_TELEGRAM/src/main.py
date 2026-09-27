import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.routers.notify import router
from src.clients.telegram import TelegramClient
from src.services.bot_commands import BotCommandListener

_bot_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    await TelegramClient().set_commands()

    global _bot_task
    _bot_task = asyncio.create_task(BotCommandListener().run_forever())
    try:
        yield
    finally:
        if _bot_task:
            _bot_task.cancel()


app = FastAPI(lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"message": "An internal server error occurred."})
