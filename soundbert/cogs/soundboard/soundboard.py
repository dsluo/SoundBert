import asyncio
import logging
import shutil
import time
from collections import OrderedDict
from pathlib import Path

import asyncpg
import discord
import youtube_dl
from discord import VoiceClient
from discord.ext import commands

from . import exceptions
from .checks import is_soundmaster, is_soundplayer
from ..utils.humantime import humanduration, TimeUnits
from ..utils.reactions import yes
from ...soundbert import SoundBert

log = logging.getLogger(__name__)


class SoundBoard(commands.Cog):
    def __init__(self, bot: 'SoundBert'):
        self.sound_path = Path(bot.config['soundboard']['path'])
        self.bot = bot

        self.playing = {}

        if not self.sound_path.is_dir():
            self.sound_path.mkdir()

    @staticmethod
    async def get_length(file: Path):
        args = '-show_entries format=duration -of default=noprint_wrappers=1:nokey=1'.split() + [str(file)]
        proc = await asyncio.create_subprocess_exec(
            'ffprobe', *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )
        out = await proc.stdout.read()
        length = out.decode().strip()
        await proc.wait()

        return float(length)

    @commands.command(aliases=['!'])
    @commands.check(is_soundplayer)
    async def play(self, ctx: commands.Context, name: str, *, args=None):
        """
        Play a sound.

        :param name: The name of the sound to play.
        :param args: The volume/speed of playback, in format v[XX%] s[SS%]. e.g. v50 s100 for 50% sound, 100% speed.
        """
        try:
            channel: discord.VoiceChannel = ctx.author.voice.channel
        except AttributeError:
            raise exceptions.NoChannel()

        async with self.bot.pool.acquire() as conn:
            sound = await conn.fetchval(
                '''
                SELECT (s.filename, s.id)
                FROM sounds s INNER JOIN sound_names sn ON s.id = sn.sound_id
                WHERE sn.guild_id = $1 AND sn.name = $2
                ''',
                ctx.guild.id,
                name.lower()
            )

            if sound is None:
                results = await self._search(ctx.guild.id, name, conn)
                if len(results) > 0:
                    results = '\n'.join(results)
                    raise exceptions.SoundDoesNotExist(name, results)
                else:
                    raise exceptions.SoundDoesNotExist(name)

            filename, id = sound

        file = self.sound_path / str(ctx.guild.id) / filename

        volume = None
        speed = None
        seek = None

        if args is not None:
            for arg in args.split():
                if volume is None and arg.startswith('v'):
                    try:
                        volume = int(arg[1:-1] if arg.endswith('%') else arg[1:])
                        if volume < 0:
                            raise exceptions.NegativeVolume()
                    except ValueError:
                        raise exceptions.BadPlaybackArgs(args)
                elif speed is None and arg.startswith('s'):
                    try:
                        speed = int(arg[1:-1] if arg.endswith('%') else arg[1:])
                        if speed < 0:
                            raise exceptions.NegativeSpeed()
                    except ValueError:
                        raise exceptions.BadPlaybackArgs(args)
                elif arg.startswith('t'):
                    try:
                        split = args[1:].split(':', maxsplit=2)
                        hours, mins, secs = ['0'] * (3 - len(split)) + split

                        # prevents command line injection
                        hours = int(hours or 0)
                        mins = int(mins or 0)
                        secs = int(secs or 0)

                        # if any one of them are > 60, resolve it
                        carry, secs = divmod(secs, 60)
                        carry, mins = divmod(mins + carry, 60)
                        hours += carry

                        seek = f'{hours}:{mins:02}:{secs:02}' if hours or mins or secs else None
                    except ValueError:
                        raise exceptions.BadPlaybackArgs(args)

        if volume is None:
            volume = 100

        log.debug(
            f'Playing sound {name} ({id}) in #{channel.name} ({channel.id}) of guild {ctx.guild.name} ({ctx.guild.id}).'
        )

        log.debug('Connecting to voice channel.')
        vclient: VoiceClient = ctx.guild.voice_client or await channel.connect()
        await vclient.move_to(channel)

        source = discord.FFmpegPCMAudio(
            str(file),
            before_options=f'-ss {seek}' if seek else None,
            options=f'-filter:a "atempo={speed / 100}"' if speed else None
        )
        source = discord.PCMVolumeTransformer(source, volume=volume / 100)

        async def stop():
            log.debug('Stopping playback.')
            await vclient.disconnect(force=True)

            async with self.bot.pool.acquire() as conn:
                await conn.execute(
                    '''
                    UPDATE sounds s
                    SET stopped = stopped + 1
                    FROM sound_names sn
                    WHERE s.id = sn.id AND sn.guild_id = $1 AND sn.name = $2
                    ''',
                    ctx.guild.id,
                    name.lower()
                )

        def wrapper(error):
            try:
                # todo: this could result in a race condition if a sound is played very soon after stopping i think
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
                'UPDATE sounds SET played = played + 1 FROM sound_names WHERE guild_id = $1 AND name = $2',
                ctx.guild.id,
                name.lower()
            )

        log.debug('Starting playback.')
        vclient.play(source=source, after=wrapper)

    @commands.command()
    @commands.check(is_soundmaster)
    async def add(self, ctx: commands.Context, name: str, link: str = None):
        """
        Add a new sound to the soundboard.

        :param name: The name of the new sound.
        :param link: Download link to new sound. If omitted, command must be called in the comment of an attachment.
        """
        # Resolve download url.
        if link is None:
            try:
                link = ctx.message.attachments[0].url
            except (IndexError, KeyError):
                raise exceptions.NoDownload()

        async with self.bot.pool.acquire() as conn:
            # Disallow duplicate names
            exists = await conn.fetchval(
                'SELECT EXISTS(SELECT 1 FROM sound_names WHERE guild_id = $1 AND name = $2)',
                ctx.guild.id,
                name.lower()
            )

            if exists:
                raise exceptions.SoundExists(name)

            # Download file
            await ctx.trigger_typing()

            def download_sound(url):
                log.debug(f'Downloading from {url}.')
                options = {
                    'format':            'bestaudio/best',
                    'postprocessors':    [{
                        'key':            'FFmpegExtractAudio',
                        'preferredcodec': 'mp3'
                    }],
                    'outtmpl':           f'{time.time()}_%(id)s.%(ext)s',
                    'restrictfilenames': True,
                    'default_search':    'error',
                    'logger':            log
                }
                yt = youtube_dl.YoutubeDL(options)
                info = yt.extract_info(url)

                # workaround for post-processed filenames
                # https://github.com/ytdl-org/youtube-dl/issues/5710
                filename = yt.prepare_filename(info)
                unprocessed = Path(filename)
                postprocessed = Path('.').glob(f'{unprocessed.stem}*')

                try:
                    file = next(postprocessed)
                except StopIteration:
                    raise FileNotFoundError("Couldn't find postprocessed file.")

                return file

            try:
                file = await self.bot.loop.run_in_executor(None, download_sound, link)
            except (youtube_dl.DownloadError, FileNotFoundError):
                raise exceptions.DownloadError()

            length = await self.get_length(file)

            server_dir = self.sound_path / str(ctx.guild.id)

            if not server_dir.exists():
                server_dir.mkdir()

            try:
                shutil.move(str(file), str(server_dir / file.name))
            except FileExistsError:
                file.unlink()
                raise exceptions.SoundExists(name)

            async with conn.transaction():
                sound_id = await conn.fetchval(
                    '''
                    INSERT INTO sounds(filename, uploader, source, upload_time, length)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                    ''',
                    file.name,
                    ctx.author.id,
                    link,
                    ctx.message.created_at,
                    length
                )

                await conn.execute(
                    'INSERT INTO sound_names(sound_id, guild_id, name) VALUES ($1, $2, $3)',
                    sound_id,
                    ctx.guild.id,
                    name.lower(),
                )
        await yes(ctx)

    @commands.command()
    @commands.check(is_soundmaster)
    async def alias(self, ctx: commands.Context, name: str, alias: str):
        """
        Allows sounds to be played by a different name.

        :param name: The sound to alias.
        :param alias: The alias to assign
        """
        async with self.bot.pool.acquire() as conn:
            try:
                exists = await conn.fetchval(
                    '''
                    INSERT INTO sound_names(sound_id, guild_id, name, is_alias)
                        SELECT sound_id, $1, $3, TRUE
                        FROM sound_names
                        WHERE guild_id = $1 AND name = $2
                    RETURNING sound_id
                    ''',
                    ctx.guild.id,
                    name,
                    alias
                )

                if exists is not None:
                    await yes(ctx)
                else:
                    raise exceptions.SoundDoesNotExist(name)
            except asyncpg.UniqueViolationError:
                raise exceptions.SoundExists(alias)

    @commands.command(aliases=['del', 'rm'])
    @commands.check(is_soundmaster)
    async def delete(self, ctx: commands.Context, name: str):
        """
        Delete a sound.

        :param name: The name of the sound to delete.
        """
        async with self.bot.pool.acquire() as conn:
            filename = await conn.fetchval(
                '''
                SELECT filename
                FROM sounds s INNER JOIN sound_names sn ON s.id = sn.sound_id
                WHERE sn.guild_id = $1 AND sn.name = $2''',
                ctx.guild.id,
                name.lower()
            )
            if filename is None:
                raise exceptions.SoundDoesNotExist(name)
            else:
                await conn.execute(
                    '''
                    DELETE FROM sounds 
                    USING sound_names
                    WHERE guild_id = $1 AND filename = $2 AND sound_id = sounds.id
                    ''',
                    ctx.guild.id,
                    filename
                )

        file = self.sound_path / str(ctx.guild.id) / filename
        file.unlink()
        await yes(ctx)

    @commands.command(aliases=['mv'])
    @commands.check(is_soundmaster)
    async def rename(self, ctx: commands.Context, name: str, new_name: str):
        """
        Rename a sound or alias.

        :param name: The name of the sound/alias to rename.
        :param new_name: The new name.
        """
        async with self.bot.pool.acquire() as conn:
            try:
                exists = await conn.fetchval(
                    'UPDATE sound_names SET name = $3 WHERE guild_id = $1 AND name = $2 RETURNING id',
                    ctx.guild.id,
                    name,
                    new_name
                )
                if exists is not None:
                    await yes(ctx)
                else:
                    raise exceptions.SoundDoesNotExist(name)
            except asyncpg.UniqueViolationError:
                raise exceptions.SoundExists(new_name)

    @commands.command(aliases=['ls'])
    @commands.check(is_soundplayer)
    async def list(self, ctx: commands.Context):
        """
        List all the sounds on the soundboard.
        """
        async with self.bot.pool.acquire() as conn:
            sounds = await conn.fetch(
                'SELECT name FROM sound_names WHERE guild_id = $1 AND NOT is_alias ORDER BY name',
                ctx.guild.id
            )
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
                if len(message) + len(line) > 2000:
                    await ctx.send(message)
                    message = ''
                message += line

        if message:
            await ctx.send(message)

    @commands.command()
    @commands.check(is_soundplayer)
    async def stop(self, ctx: commands.Context):
        """
        Stop playback of the current sound.
        """
        try:
            await self.playing.pop(ctx.guild.id)
        except KeyError:
            # nothing was playing
            pass

    @commands.command(aliases=['stat'])
    @commands.check(is_soundplayer)
    async def info(self, ctx: commands.Context, name: str):
        """
        Get info about a sound.

        :param name: The sound to get info about.
        """
        async with self.bot.pool.acquire() as conn:
            sound = await conn.fetchval(
                '''
                SELECT (sound_id, played, stopped, source, uploader, upload_time, length) 
                FROM sounds s INNER JOIN sound_names sn ON s.id = sn.sound_id 
                WHERE sn.guild_id = $1 AND sn.name = $2
                ''',
                ctx.guild.id,
                name.lower()
            )

            if sound is None:
                raise exceptions.SoundDoesNotExist(name)

            id, played, stopped, source, uploader_id, upload_time, length = sound

            names = [
                record['name']
                for record in await conn.fetch(
                    'SELECT name FROM sound_names WHERE sound_id = $1 ORDER BY is_alias, name',
                    id
                )
            ]

            name, *aliases = names

        embed = discord.Embed()
        embed.title = name

        if uploader_id:
            uploader = self.bot.get_user(uploader_id) or (await self.bot.fetch_user(uploader_id))
            embed.set_author(name=uploader.name, icon_url=uploader.avatar_url)
            embed.add_field(name='Uploader', value=f'<@{uploader_id}>')
        if upload_time:
            embed.set_footer(text='Uploaded at')
            embed.timestamp = upload_time
        if source:
            embed.add_field(name='Source', value=source)
        embed.add_field(name='Played', value=played)
        embed.add_field(name='Stopped', value=stopped)
        embed.add_field(name='Length', value=humanduration(length, TimeUnits.MILLISECONDS))
        if aliases:
            embed.add_field(name='Aliases', value=', '.join(aliases))

        await ctx.send(embed=embed)

    @commands.command()
    @commands.check(is_soundplayer)
    async def rand(self, ctx: commands.Context, *, args=None):
        """
        Play a random sound.

        :param args: The volume/speed of playback, in format v[XX%] s[SS%]. e.g. v50 s100 for 50% sound, 100% speed.
        """
        async with self.bot.pool.acquire() as conn:
            name = await conn.fetchval(
                'SELECT name FROM sound_names WHERE guild_id = $1 AND NOT is_alias ORDER BY RANDOM() LIMIT 1',
                ctx.guild.id
            )
        log.debug(f'Playing random sound {name}.')
        await ctx.invoke(self.play, name, args=args)

    @commands.command(aliases=['find'])
    @commands.check(is_soundplayer)
    async def search(self, ctx: commands.Context, query: str):
        """
        Search for a sound.
        """

        async with self.bot.pool.acquire() as conn:
            results = await self._search(ctx.guild.id, query, conn)

        if not results:
            await ctx.send('No results found.')
        else:
            response = f'Found {len(results)} result{"s" if len(results) != 1 else ""}.\n' + '\n'.join(results)
            await ctx.send(response)

    async def _search(self, guild_id, query, connection, alias=None, threshold=0.1, limit=10):
        """
        Search for a sound.

        :param guild_id: The guild ID.
        :param query: The sound to search.
        :param connection: The database connection.
        :param alias: True for only aliases, False for no aliases, None for any.
        :param threshold: The similarity threshold.
        :param limit: Maximum number of results to produce.
        :return:
        """
        await connection.execute(f'SET pg_trgm.similarity_threshold = {threshold};')

        if alias is None:
            results = await connection.fetch(
                '''
                SELECT name
                FROM sound_names
                WHERE guild_id = $1 AND name % $2
                ORDER BY similarity(name, $2) DESC
                LIMIT $3
                ''',
                guild_id,
                query,
                limit,
            )
        else:
            results = await connection.fetch(
                '''
                SELECT name
                FROM sound_names
                WHERE guild_id = $1 AND is_alias = $4 AND name % $2
                ORDER BY similarity(name, $2) DESC
                LIMIT $3
                ''',
                guild_id,
                query,
                limit,
                alias
            )

        results = [record['name'] for record in results]

        return results
