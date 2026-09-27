import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from src.clients.groq_client import GroqClient, GroqExtractionError
from src.schemas.extraction import ExtractionResult

router = APIRouter(prefix="/extract", tags=["Extract"])


@router.post("", response_model=ExtractionResult)
async def extract(
    caption: str | None = Form(None),
    image: UploadFile | None = File(None),
):
    image_bytes = await image.read() if image is not None else None
    content_type = (image.content_type if image is not None else None) or "image/jpeg"

    client = GroqClient()
    try:
        raw = await client.extract(caption or "", image_bytes, content_type)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Groq API error: {e.response.text}") from e
    except GroqExtractionError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return ExtractionResult(**raw)
