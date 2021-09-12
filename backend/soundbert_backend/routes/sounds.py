import asyncio
from pathlib import Path
from typing import List

import youtube_dl
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from ..db.engine import get_session
from ..db.models import Sound
from ..schema import SoundCreate, SoundRead, SoundUpdate
from ..storage import get_storage, SoundStorage

router = APIRouter(
        prefix='/sounds',
        tags=['sounds']
)


def _download_sound(url: str):
    options = {
        'format':            'webm[abr>0]/bestaudio/best',
        'restrictfilenames': True,
        'default_search':    'error'
    }

    yt = youtube_dl.YoutubeDL(options)
    info = yt.extract_info(url, download=True)
    filename = yt.prepare_filename(info)

    return info, Path(filename)


@router.post('/', response_model=SoundRead, status_code=status.HTTP_201_CREATED)
async def create_sound(
        create: SoundCreate,
        db: AsyncSession = Depends(get_session),
        storage: SoundStorage = Depends(get_storage)):
    # see if the sound exists already to avoid unnecessary downloads.
    exists = await db.execute(
            select(1)
                .select_from(Sound)
                .where(Sound.guild_id == create.guild_id)
                .where(Sound.name == create.name)
                .exists()
                .select()
    )
    if exists.scalar():
        raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f'Sound named "{create.name}" already exists for guild ID {create.guild_id}'
        )
    sound = Sound(**create.dict())

    loop = asyncio.get_running_loop()
    try:
        info, file = await loop.run_in_executor(None, _download_sound, create.source)
    except youtube_dl.DownloadError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=e.args)

    sound.length = info.get('duration')

    await storage.store(create.guild_id, create.name, file)

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
async def update_sound(
        id: int,
        update: SoundUpdate,
        db: AsyncSession = Depends(get_session),
        storage: SoundStorage = Depends(get_storage)):
    sound = await db.get(Sound, id)
    if sound is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    rename_args = sound.guild_id, sound.name, update.name

    for key, value in update.dict().items():
        setattr(sound, key, value)

    await storage.rename(*rename_args)

    await db.commit()
    return sound


@router.delete('/{id}', response_model=SoundRead)
async def delete_sound(
        id: int,
        db: AsyncSession = Depends(get_session),
        storage: SoundStorage = Depends(get_storage)):
    sound = await db.get(Sound, id)
    if sound is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    await storage.delete(sound.guild_id, sound.name)

    await db.delete(sound)
    await db.commit()
    return sound
