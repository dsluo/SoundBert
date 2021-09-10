from sqlalchemy import Column, BigInteger, String, Text, DateTime, func, ForeignKey, Float, Integer
from sqlalchemy.orm import relationship

from .base import Base
from .. import settings

class TimestampMixin:
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

class Guild(Base, TimestampMixin):
    __tablename__ = 'guilds'

    id = Column(BigInteger, primary_key=True, autoincrement=False)
    prefix = Column(String(length=8), default=settings.DEFAULT_PREFIX, nullable=False)

    sounds = relationship('Sound', backref='guild')

class Sound(Base, TimestampMixin):
    __tablename__ = 'sounds'

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    guild_id = Column(BigInteger, ForeignKey('guilds.id'), nullable=False)
    source = Column(Text, nullable=False)
    uploaded_by = Column(BigInteger, nullable=False)
    length = Column(Float, nullable=False)

    playbacks = relationship('Playback', backref='sound')

class Playback(Base, TimestampMixin):
    __tablename__ = 'playbacks'

    id = Column(Integer, primary_key=True)
    sound_id = Column(ForeignKey('sounds.id'), nullable=False)

    started_at = Column(DateTime(timezone=True), nullable=False)
    started_by = Column(BigInteger, nullable=False)

    stopped_at = Column(DateTime(timezone=True))
    stopped_by = Column(BigInteger)