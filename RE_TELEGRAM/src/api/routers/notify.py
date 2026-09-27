import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from src.clients.telegram import TelegramClient, is_video
from src.schemas.notification import NotifyResponseSchema

router = APIRouter(prefix="/notify", tags=["Notify"])


def _build_text(profile_username: str, post_url: str, caption: str | None) -> str:
    lines = [f"Новый пост: @{profile_username}"]
    if caption:
        # Раньше здесь было " ".join(caption.split()) — оно схлопывало ЛЮБые пробельные
        # символы, включая переносы строк, в один пробел. Это было нормально для сырой
        # подписи Instagram, но теперь сюда же приходит уже готовый многострочный текст
        # (цена/тип/площадь на разных строках), и эта нормализация просто уничтожала все
        # переносы. Больше не трогаем — только убираем пробелы по краям.
        lines.append(caption.strip())
    lines.append(post_url)
    return "\n\n".join(lines)


@router.post("", response_model=NotifyResponseSchema)
async def notify(
    profile_username: str = Form(...),
    post_url: str = Form(...),
    caption: str | None = Form(None),
    target_chat_id: str | None = Form(None),
    media: list[UploadFile] = File(default=[]),
):
    text = _build_text(profile_username, post_url, caption)
    client = TelegramClient()

    files: list[tuple[str, bytes]] = []
    for item in media:
        content = await item.read()
        files.append((item.filename or "file", content))

    try:
        if len(files) > 1:
            await client.send_media_group(files, text, target_chat_id=target_chat_id)
        elif len(files) == 1:
            filename, content = files[0]
            if is_video(filename):
                await client.send_video(filename, content, text, target_chat_id=target_chat_id)
            else:
                await client.send_photo(filename, content, text, target_chat_id=target_chat_id)
        else:
            await client.send_text(text, target_chat_id=target_chat_id)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Telegram API error: {e.response.text}") from e

    return NotifyResponseSchema()
