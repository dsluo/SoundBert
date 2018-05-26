import asyncio
import hashlib
import time
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles
import aiohttp
import discord
from discord import VoiceClient
from discord.ext import commands

from cogs.utils.reactions import yes

if TYPE_CHECKING:
    from soundbert import SoundBert


class SoundBoard:
    def __init__(self, sound_path: Path, bot: 'SoundBert'):
        self.sound_path = sound_path.absolute()
        self.bot = bot

        self.playing = {}

        if not self.sound_path.is_dir():
            self.sound_path.mkdir()

    @commands.command(
        aliases=['!', 'p']
    )
    async def play(self, ctx: commands.Context, name: str, *, args=None):
        """
        Play a sound.

        :param name: The name of the sound to play.
        :param args: The volume/speed of playback, in format v[XX%] s[SS%]. e.g. v50 s100.
        """
        if not name:
            raise commands.BadArgument('Invalid sound name.')

        async with self.bot.pool.acquire() as conn:
            filename = await conn.fetchval(
                'SELECT filename FROM sounds WHERE guild_id = $1 AND name = $2',
                ctx.guild.id,
                name.lower()
            )

        if filename is None:
            raise commands.BadArgument(f'Sound **{name}** does not exist.')

        file = self.sound_path / str(ctx.guild.id) / filename

        volume = None
        speed = None

        if args is not None:
            for arg in args.split():
                if volume is None and arg.startswith('v'):
                    try:
                        volume = int(arg[1:-1] if arg.endswith('%') else arg[1:])
                        if volume < 0:
                            raise commands.BadArgument('Volume cannot be less than 0%.')
                    except ValueError:
                        raise commands.BadArgument(f'Could not parse `{args}`.')
                elif speed is None and arg.startswith('s'):
                    try:
                        speed = int(arg[1:-1] if arg.endswith('%') else arg[1:])
                        if not (50 <= speed <= 200):
                            raise commands.BadArgument('Speed must be between 50% and 200%.')
                    except ValueError:
                        raise commands.BadArgument(f'Could not parse `{args}`.')
        if volume is None:
            volume = 100
        if speed is None:
            speed = 100

        channel = ctx.author.voice.channel

        if channel is None:
            raise commands.CommandError('No target channel.')

        vclient: VoiceClient = ctx.guild.voice_client or await channel.connect()
        vclient.move_to(channel)

        source = discord.FFmpegPCMAudio(str(file),
                                        options=f'-filter:a "atempo={speed/100}"')
        source = discord.PCMVolumeTransformer(source, volume=volume / 100)

        async def stop():
            await vclient.disconnect(force=True)
            return name

        def wrapper(error):
            try:
                coro = self.playing.pop(ctx.guild.id)
                future = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
                try:
                    future.result()
                except:
                    pass
            except KeyError:
                # sound was stopped with stop command, so do nothing.
                pass

        self.playing[ctx.guild.id] = stop()

        async with self.bot.pool.acquire() as conn:
            await conn.execute(
                'UPDATE sounds SET played = played + 1 WHERE guild_id = $1 AND name = $2',
                ctx.guild.id,
                name
            )

        vclient.play(source=source, after=wrapper)

    @commands.command(
        aliases=['+', 'a']
    )
    async def add(self, ctx: commands.Context, name: str, link: str = None):
        """
        Add a new sound to the soundboard.

        :param name: The name of the new sound.
        :param link: Download link to new sound. If omitted, command must be called in the comment of an attachment.
        """
        # Disallow duplicate names
        async with self.bot.pool.acquire() as conn:
            exists = await conn.fetchval(
                'SELECT EXISTS(SELECT 1 FROM sounds WHERE guild_id = $1 AND name = $2)',
                ctx.guild.id,
                name.lower()
            )

            if exists:
                raise commands.BadArgument(f'Sound named `{name}` already exists.')

            # Resolve download url.
            if link is None:
                try:
                    link = ctx.message.attachments[0].url
                except (IndexError, KeyError):
                    raise commands.BadArgument('Download link or file attachment required.')

            # Download file
            with ctx.typing():
                async with aiohttp.ClientSession() as session:
                    async with session.get(link) as resp:
                        if resp.status == 200:

                            # Write response to temporary file and moves it to the /sounds directory when done.
                            # Filename = blake2 hash of file
                            hash = hashlib.blake2b()
                            temp_file = Path(f'./tempsound_{ctx.guild.id}_{time.time()}')
                            async with aiofiles.open(temp_file, 'wb') as f:
                                while True:
                                    chunk = await resp.content.read(1024)
                                    if not chunk:
                                        break
                                    hash.update(chunk)
                                    await f.write(chunk)

                            filename = hash.hexdigest().upper()

                            try:
                                server_dir = self.sound_path / str(ctx.guild.id)

                                if not server_dir.exists():
                                    server_dir.mkdir()
                            except OSError:
                                raise commands.BadArgument('Error while creating guild directory.')

                            try:
                                temp_file.rename(server_dir / filename)
                            except FileExistsError:
                                temp_file.unlink()
                                raise commands.BadArgument('Sound already exists.')

                            await conn.execute(
                                'INSERT INTO guild(id) VALUES ($1) ON CONFLICT DO NOTHING',
                                ctx.guild.id
                            )

                            await conn.execute(
                                'INSERT INTO sounds(guild_id, name, filename) VALUES ($1, $2, $3)',
                                ctx.guild.id,
                                name.lower(),
                                filename
                            )
                            await yes(ctx)

                        else:
                            raise commands.CommandError(f'Error while downloading: {resp.status}: {resp.reason}.')
                        # probably not needed because context manager
                        # await resp.release()

    @commands.command(
        aliases=['-', 'd', 'del']
    )
    async def delete(self, ctx: commands.Context, name: str):
        """
        Delete a sound.

        :param name: The name of the sound to delete.
        """
        async with self.bot.pool.acquire() as conn:
            async with conn.transaction():
                filename = await conn.fetchval(
                    'SELECT filename FROM sounds WHERE guild_id = $1 AND name = $2',
                    ctx.guild.id,
                    name.lower()
                )
                if filename is None:
                    raise commands.BadArgument(f'Sound **{name}** does not exist.')
                else:
                    await conn.execute(
                        'DELETE FROM sounds WHERE guild_id = $1 AND filename = $2',
                        ctx.guild.id,
                        filename
                    )

        file = self.sound_path / str(ctx.guild.id) / filename
        file.unlink()
        await yes(ctx)

    @commands.command(
        aliases=['~', 'r']
    )
    async def rename(self, ctx: commands.Context, name: str, new_name: str):
        """
        Rename a sound.

        :param name: The name of the sound to rename.
        :param new_name: The new name.
        """
        async with self.bot.pool.acquire() as conn:
            async with conn.transaction():
                exists = await conn.fetchval(
                    'SELECT EXISTS(SELECT 1 FROM sounds WHERE guild_id = $1 AND name = $2)',
                    ctx.guild.id,
                    name.lower()
                )
                if not exists:
                    raise commands.BadArgument(f'Sound **{name}** does not exist.')
                else:
                    await conn.execute(
                        'UPDATE sounds SET name = $3 WHERE guild_id = $1 AND name = $2',
                        ctx.guild.id,
                        name.lower(),
                        new_name.lower()
                    )

        await yes(ctx)

    @commands.command()
    async def list(self, ctx: commands.Context):
        """
        List all the sounds on the soundboard.
        """
        async with self.bot.pool.acquire() as conn:
            sounds = await conn.fetch('SELECT name FROM sounds WHERE guild_id = $1 ORDER BY name', ctx.guild.id)
        if len(sounds) == 0:
            message = 'No sounds yet.'
        else:
            split = OrderedDict()
            for sound in sounds:
                name = sound['name']
                first = name[0].lower()
                if first not in 'abcdefghijklmnopqrstuvwxyz':
                    first = '#'
                if first not in split.keys():
                    split[first] = [name]
                else:
                    split[first].append(name)

            message = '**Sounds**\n'

            for letter, sounds_ in split.items():
                line = f'**`{letter}`**: {", ".join(sounds_)}\n'
                message += line

        await ctx.send(message)

    @commands.command()
    async def stop(self, ctx: commands.Context):
        """
        Stop playback of the current sound.
        """
        coro = self.playing.pop(ctx.guild.id)
        name = await coro

        async with self.bot.pool.acquire() as conn:
            await conn.execute(
                'UPDATE sounds SET stopped = stopped + 1 WHERE guild_id = $1 AND name = $2',
                ctx.guild.id,
                name.lower()
            )

    @commands.command()
    async def stat(self, ctx: commands.Context, name: str):
        """
        Get stats of a sound.

        :param name: The sound to get stats for.
        """
        async with self.bot.pool.acquire() as conn:
            sound = await conn.fetchval(
                'SELECT (played, stopped) FROM sounds WHERE guild_id = $1 AND name = $2',
                ctx.guild.id,
                name.lower()
            )

        if sound is None:
            raise commands.BadArgument(f'Sound **{name}** does not exist.')

        played, stopped = sound

        resp = f'**{name}** stats:\nPlayed {played} times.\nStopped {stopped} times.'
        await ctx.send(resp)

    @commands.command()
    async def rand(self, ctx: commands.Context, *, args=None):
        """
        Play a random sound.

        :param args: The volume/speed of playback, in format v[XX%] s[SS%]. e.g. v50 s100.
        """
        async with self.bot.pool.acquire() as conn:
            name = await conn.fetchval(
                'SELECT name FROM sounds WHERE guild_id = $1 ORDER BY RANDOM() LIMIT 1',
                ctx.guild.id
            )
        await ctx.invoke(self.play, name, args=args)

    @commands.command(
        hidden=True
    )
    @commands.is_owner()
    async def id(self, ctx: commands.Context, name, guild_id=None):
        async with self.bot.pool.acquire() as conn:
            filename = await conn.fetchval(
                'SELECT filename FROM sounds WHERE guild_id = $1 AND name = $2',
                guild_id or ctx.guild.id,
                name.lower()
            )

        await ctx.send(str(filename))


def setup(bot):
    sound_path = Path(bot.config.get('sound_path', './sounds'))
    bot.add_cog(SoundBoard(sound_path, bot))
