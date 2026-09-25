from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from src.services.source import SourceService
from src.services.property import PropertyService
from src.db.session import async_session_maker
from src.schemas.source import SourceAddSchema
from src.schemas.raw_post import RawPostResponseSchema

app = FastAPI()

class SourceRequest(BaseModel):
    profile_username: str

class ParseRequest(BaseModel):
    profile_username: str

async def get_db():
    async with async_session_maker() as session:
        yield session

@app.post("/sources")
async def add_source(source: SourceRequest, db=Depends(get_db)):
    service = SourceService(db)
    try:
        result = await service.add_source(SourceAddSchema(profile_username=source.profile_username))
        return {"status": "success", "source_id": result.id, "message": f"Source {source.profile_username} added"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/parse")
async def parse_profile(request: ParseRequest, db=Depends(get_db)):
    service = PropertyService(db)
    try:
        raw_posts = await service.collect_properties(request.profile_username)
        saved_count = await service.raw_post_service.save_raw_posts(raw_posts)
        return {"status": "success", "posts_count": saved_count, "message": f"Parsed {len(raw_posts)} posts"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/posts", response_model=List[RawPostResponseSchema])
async def get_posts(db=Depends(get_db)):
    service = PropertyService(db)
    try:
        raw_posts = await service.raw_post_service.get_raw_posts()
        return raw_posts
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok"}
