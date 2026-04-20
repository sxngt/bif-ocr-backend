from datetime import datetime

from pydantic import BaseModel, Field


class UsageLogResponse(BaseModel):
    id: str
    title: str
    file_name: str
    s3_key: str | None
    compact_result: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UsageLogListItem(BaseModel):
    id: str
    title: str
    file_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class UsageLogUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
