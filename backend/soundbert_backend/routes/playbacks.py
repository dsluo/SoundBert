from http.client import HTTPException

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from ..db.base import get_session
from ..db.models import Playback
from ..schema import PlaybackRead, PlaybackCreate, PlaybackUpdate

router = APIRouter(
    prefix='/playbacks',
    tags=['playbacks']
)


@router.post('/', response_model=PlaybackRead)
def create_playback(create: PlaybackCreate, db: AsyncSession = Depends(get_session)):
    playback = Playback(**create.dict())

    db.add(playback)
    await db.commit()
    return playback

@router.get('/{id}', response_model=PlaybackRead)
def get_playback(id: int, db: AsyncSession = Depends(get_session)):
    playback = await db.get(Playback, id)
    if playback is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    return playback

@router.put('/{id}', response_model=PlaybackRead)
def update_playback(id: int, update: PlaybackUpdate, db: AsyncSession = Depends(get_session)):
    playback = await db.get(Playback, id)
    if playback is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    for key, value in update.dict().items():
        setattr(playback, key, value)

    await db.commit()
    return playback

@router.delete('/{id}', response_model=PlaybackRead)
def delete_playback(id: int, db: AsyncSession = Depends(get_session)):
    playback = await db.get(Playback, id)
    if playback is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    await db.delete(playback)
    await db.commit()
    return playback