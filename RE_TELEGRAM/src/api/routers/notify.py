import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from src.clients.telegram import TelegramClient
from src.schemas.notification import NotifyResponseSchema

router = APIRouter(prefix="/notify", tags=["Notify"])

TEXT_SNIPPET_LIMIT = 300


def _build_text(profile_username: str, post_url: str, caption: str | None) -> str:
    lines = [f"Новый пост: @{profile_username}"]
    if caption:
        snippet = " ".join(caption.split())
        if len(snippet) > TEXT_SNIPPET_LIMIT:
            snippet = snippet[:TEXT_SNIPPET_LIMIT] + "…"
        lines.append(snippet)
    lines.append(post_url)
    return "\n\n".join(lines)


@router.post("", response_model=NotifyResponseSchema)
async def notify(
    profile_username: str = Form(...),
    post_url: str = Form(...),
    caption: str | None = Form(None),
    photo: UploadFile | None = File(None),
):
    text = _build_text(profile_username, post_url, caption)
    client = TelegramClient()

    try:
        if photo is not None:
            content = await photo.read()
            await client.send_photo(photo.filename or "photo.jpg", content, text)
        else:
            await client.send_text(text)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Telegram API error: {e.response.text}") from e

    return NotifyResponseSchema()
