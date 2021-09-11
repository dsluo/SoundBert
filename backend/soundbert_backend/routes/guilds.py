from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from ..db.engine import get_session
from ..db.models import Guild
from ..schema import GuildRead, GuildCreate, GuildUpdate

router = APIRouter(
        prefix='/guilds',
        tags=['gulids']
)


@router.post('/', response_model=GuildRead, status_code=status.HTTP_201_CREATED)
async def create_guild(create: GuildCreate, db: AsyncSession = Depends(get_session)):
    guild = Guild(**create.dict())

    db.add(guild)
    await db.commit()
    return guild


@router.get('/{id}', response_model=GuildRead)
async def get_guild(id: int, db: AsyncSession = Depends(get_session)):
    guild = await db.get(Guild, id)
    if guild is None:
        raise HTTPException(404, 'Not found.')

    return guild


@router.put('/{id}', response_model=GuildRead)
async def update_guild(id: int, update: GuildUpdate, db: AsyncSession = Depends(get_session)):
    guild = await db.get(Guild, id)
    if guild is None:
        raise HTTPException(404, 'Not found.')

    for key, value in update.dict().items():
        setattr(guild, key, value)

    await db.commit()
    return guild


@router.delete('/{id}', response_model=GuildRead)
async def delete_guild(id: int, db: AsyncSession = Depends(get_session)):
    guild = await db.get(Guild, id)
    if guild is None:
        raise HTTPException(404, 'Not found.')

    await db.delete(guild)
    await db.commit()
    return guild
