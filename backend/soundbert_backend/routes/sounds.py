from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from ..db.base import get_session
from ..db.models import Sound
from ..schema import SoundCreate, SoundRead, SoundUpdate

router = APIRouter(
        prefix='/sounds',
        tags=['sounds']
)


@router.post('/', response_model=SoundRead)
async def create_sound(create: SoundCreate, db: AsyncSession = Depends(get_session)):
    sound = Sound(**create.dict())

    sound.length = 0

    db.add(sound)
    await db.commit()
    return sound


@router.get('/', response_model=List[SoundRead])
async def list_sounds(guild_id: int, offset: int = 0, limit: int = 100, db: AsyncSession = Depends(get_session)):
    query = select(Sound). \
        where(Sound.guild_id == guild_id). \
        order_by(Sound.name). \
        offset(offset). \
        limit(limit)

    cursor = await db.execute(query)

    return cursor.scalars().all()


@router.get('/{id}', response_model=SoundRead)
async def get_sound(id: int, db: AsyncSession = Depends(get_session)):
    sound = await db.get(Sound, id)
    if sound is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    return sound


@router.put('/{id}', response_model=SoundRead)
async def update_sound(id: int, update: SoundUpdate, db: AsyncSession = Depends(get_session)):
    sound = await db.get(Sound, id)
    if sound is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    for key, value in update.dict().items():
        setattr(sound, key, value)

    await db.commit()
    return sound


@router.delete('/{id}', response_model=SoundRead)
async def delete_sound(id: int, db: AsyncSession = Depends(get_session)):
    sound = await db.get(Sound, id)
    if sound is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    await db.delete(sound)
    await db.commit()
    return sound
