from datetime import datetime
from typing import Optional

import pydantic
from pydantic import BaseModel


class TimestampMixin:
    created_at: datetime
    updated_at: datetime


class GuildCreate(BaseModel):
    id: int
    prefix: Optional[str]


class GuildRead(BaseModel, TimestampMixin):
    id: int
    prefix: str

    class Config:
        orm_mode = True


class GuildUpdate(BaseModel):
    prefix: str


class SoundCreate(BaseModel):
    name: str
    guild_id: int
    source: pydantic.AnyHttpUrl
    uploaded_by: int


class SoundRead(BaseModel, TimestampMixin):
    id: int
    name: str
    guild_id: int
    source: str
    uploaded_by: int
    length: float

    class Config:
        orm_mode = True


class SoundUpdate(BaseModel):
    name: str


class PlaybackCreate(BaseModel):
    sound_id: int
    started_by: int


class PlaybackRead(BaseModel, TimestampMixin):
    id: int
    sound_id: int
    started_at: datetime
    started_by: int
    stopped_at: datetime
    stopped_by: int

    class Config:
        orm_mode = True


class PlaybackUpdate(BaseModel, TimestampMixin):
    stopped_at: datetime
    stopped_by: int
