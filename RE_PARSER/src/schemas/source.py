from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl


class SourceAddSchema(BaseModel):
    source_type: str = "instagram"
    profile_username: str
    profile_url: HttpUrl | None = None
    is_active: bool = True
    notes: str | None = None


class SourceResponseSchema(SourceAddSchema):
    id: int
    last_checked_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
