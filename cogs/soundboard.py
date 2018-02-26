import asyncio
import hashlib
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING

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
            filename = await conn.fetchval('SELECT filename FROM sounds WHERE name = $1', name)

        if filename is None:
            raise commands.BadArgument(f'Sound `{filename}` not found.')

        file = self.sound_path / filename

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
        else:
            volume = 100
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
            async with self.bot.pool.acquire() as conn:
                await conn.execute('UPDATE sounds SET played = played + 1 WHERE name = $1', name)

            return name

        coro = stop()

        def wrapper(error):
            future = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
            try:
                future.result()
            except:
                pass

        self.playing[ctx.guild.id] = coro
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
            exists = await conn.fetchval('SELECT EXISTS(SELECT 1 FROM sounds WHERE name = $1)', name)

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
                        temp_file = Path('./tempsound')
                        with temp_file.open('wb') as f:
                            while True:
                                chunk = await resp.content.read(1024)
                                if not chunk:
                                    break
                                hash.update(chunk)
                                f.write(chunk)

                        filename = hash.hexdigest().upper()

                        try:
                            temp_file.rename(self.sound_path / filename)

                            async with self.bot.pool.acquire() as conn:
                                await conn.execute('INSERT INTO sounds(name, filename) VALUES ($1, $2)',
                                                   name, filename)
                            await yes(ctx)
                        except FileExistsError:
                            raise commands.BadArgument('Sound already exists.')
                        # finally:
                        # temp_file.unlink()

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
                filename = await conn.fetchval('SELECT filename FROM sounds WHERE name = $1', name)
                if filename is None:
                    raise commands.BadArgument(f'Sound **{name}** does not exist.')
                else:
                    await conn.execute('DELETE FROM sounds WHERE filename = $1', filename)

        file = self.sound_path / filename
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
                exists = await conn.fetchval('SELECT EXISTS(SELECT 1 FROM sounds WHERE name = $1)', name)
                if not exists:
                    raise commands.BadArgument(f'Sound **{name}** does not exist.')
                else:
                    await conn.execute('UPDATE sounds SET name = $2 WHERE name = $1', name, new_name)

        await yes(ctx)

    @commands.command()
    async def list(self, ctx: commands.Context):
        """
        List all the sounds on the soundboard.
        """
        async with self.bot.pool.acquire() as conn:
            sounds = await conn.fetch('SELECT name FROM sounds ORDER BY name')
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
        name = await self.playing.pop(ctx.guild.id)

        async with self.bot.pool.acquire() as conn:
            await conn.execute('UPDATE sounds SET stopped = stopped + 1 WHERE name = $1', name)

    @commands.command()
    async def stat(self, ctx: commands.Context, name: str):
        """
        Get stats of a sound.

        :param name: The sound to get stats for.
        """
        async with self.bot.pool.acquire() as conn:
            sound = await conn.fetchval('SELECT (played, stopped) FROM sounds WHERE name = $1', name)

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
            name = await conn.fetchval('SELECT name FROM sounds ORDER BY RANDOM() LIMIT 1')
        await ctx.invoke(self.play, name, args=args)


def setup(bot):
    sound_path = Path(bot.config.get('sound_path', './sounds'))
    bot.add_cog(SoundBoard(sound_path, bot))
