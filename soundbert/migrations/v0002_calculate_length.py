import asyncio
from pathlib import Path

import asyncpg

from soundbert.cogs.soundboard.soundboard import SoundBoard


async def do_migration(conn: asyncpg.Connection, config):
    sound_path = Path(config['soundboard']['path'])

    sounds = [record['row'] async for record in conn.cursor('SELECT (guild_id, name, filename) FROM sounds')]

    lengths = await asyncio.gather(*[
        SoundBoard.get_length(sound_path / str(guild_id) / filename) for guild_id, name, filename in sounds
    ])

    parameters = [
        (length, guild_id, name) for (guild_id, name, _), length in zip(sounds, lengths)
    ]

    await conn.executemany('UPDATE sounds SET length = $1 WHERE guild_id = $2 AND name = $3', parameters)
