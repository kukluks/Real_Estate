from pydantic import BaseModel


class NotifyResponseSchema(BaseModel):
    status: str = "sent"
