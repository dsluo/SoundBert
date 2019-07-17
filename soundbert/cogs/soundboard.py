import asyncio
import hashlib
import logging
import time
from collections import OrderedDict
from pathlib import Path

import aiofiles
import discord
import youtube_dl
from discord import VoiceClient
from discord.ext import commands

from .utils.reactions import yes
from ..soundbert import SoundBert

log = logging.getLogger(__name__)


class SoundBoard(commands.Cog):
    def __init__(self, bot: 'SoundBert'):
        self.sound_path = Path(bot.config['soundboard']['path'])
        self.bot = bot

        self.playing = {}
        self.last_played = {}

        if not self.sound_path.is_dir():
            self.sound_path.mkdir()

    @commands.command(aliases=['!', 'p'])
    async def play(self, ctx: commands.Context, name: str, *, args=None):
        """
        Play a sound.

        :param name: The name of the sound to play.
        :param args: The volume/speed of playback, in format v[XX%] s[SS%]. e.g. v50 s100 for 50% sound, 100% speed.
        """
        if not name:
            raise commands.BadArgument('Invalid sound name.')

        try:
            channel = ctx.author.voice.channel
        except AttributeError:
            raise commands.CommandError('No target channel.')

        async with self.bot.pool.acquire() as conn:
            filename = await conn.fetchval(
                'SELECT filename FROM sounds WHERE guild_id = $1 AND name = $2',
                ctx.guild.id,
                name.lower()
            )

            if filename is None:
                results = await self._search(ctx.guild.id, name, conn)
                if len(results) > 0:
                    results = '\n'.join(result['name'] for result in results)
                    raise commands.BadArgument(f'Sound **{name}** does not exist. Did you mean:\n{results}')
                else:
                    raise commands.BadArgument(f'Sound **{name}** does not exist.')

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
                        raise commands.BadArgument(f'Could not parse `{args}`.')

        if volume is None:
            volume = 100

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
                    'UPDATE sounds SET stopped = stopped + 1 WHERE guild_id = $1 AND name = $2',
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
                'UPDATE sounds SET played = played + 1 WHERE guild_id = $1 AND name = $2',
                ctx.guild.id,
                name.lower()
            )

        self.last_played[ctx.guild.id] = (name, args)

        log.debug('Stopping playback.')
        vclient.play(source=source, after=wrapper)

    @commands.command(aliases=['+', 'a'])
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
                raise commands.MissingRequiredArgument('Download link or file attachment required.')

        async with self.bot.pool.acquire() as conn:
            async with conn.transaction():
                # Disallow duplicate names
                exists = await conn.fetchval(
                    'SELECT EXISTS(SELECT 1 FROM sounds WHERE guild_id = $1 AND name = $2)',
                    ctx.guild.id,
                    name.lower()
                )

                if exists:
                    raise commands.BadArgument(f'Sound named `{name}` already exists.')

                # Download file
                await ctx.trigger_typing()

                def download_sound(url):
                    options = {
                        'format':            'bestaudio/best',
                        'postprocessors':    [{
                            'key':            'FFmpegExtractAudio',
                            'preferredcodec': 'mp3'
                        }],
                        'outtmpl':           f'{time.time()}_%(id)s.%(ext)s',
                        'restrictfilenames': True,
                        'default_search':    'error',
                    }
                    yt = youtube_dl.YoutubeDL(options)
                    log.debug(f'Downloading from {url}.')
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
                except youtube_dl.DownloadError:
                    raise commands.BadArgument('Malformed download link.')
                except FileNotFoundError:
                    raise commands.CommandError('Unable to find audio file.')

                # Write response to temporary file and moves it to the /sounds directory when done.
                # Filename = blake2 hash of file
                hash = hashlib.blake2b()
                async with aiofiles.open(file, 'rb') as f:
                    while True:
                        chunk = await f.read(8192)
                        if not chunk:
                            break
                        hash.update(chunk)

                filename = hash.hexdigest().upper()

                try:
                    server_dir = self.sound_path / str(ctx.guild.id)

                    if not server_dir.exists():
                        server_dir.mkdir()
                except OSError:
                    raise commands.CommandError('Error while creating guild directory.')

                try:
                    file.rename(server_dir / filename)
                except FileExistsError:
                    file.unlink()
                    raise commands.BadArgument('Sound already exists.')

                await conn.execute(
                    'INSERT INTO guilds(id) VALUES ($1) ON CONFLICT DO NOTHING',
                    ctx.guild.id
                )

                await conn.execute(
                    'INSERT INTO sounds(guild_id, name, filename, uploader, source, upload_time) VALUES ($1, $2, $3, $4, $5, $6)',
                    ctx.guild.id,
                    name.lower(),
                    filename,
                    ctx.author.id,
                    link,
                    ctx.message.created_at
                )
                await yes(ctx)

    @commands.command(aliases=['-', 'd', 'del'])
    async def delete(self, ctx: commands.Context, name: str):
        """
        Delete a sound.

        :param name: The name of the sound to delete.
        """
        async with self.bot.pool.acquire() as conn:
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

    @commands.command(aliases=['~', 're'])
    async def rename(self, ctx: commands.Context, name: str, new_name: str):
        """
        Rename a sound.

        :param name: The name of the sound to rename.
        :param new_name: The new name.
        """
        async with self.bot.pool.acquire() as conn:
            result = await conn.execute(
                'UPDATE sounds SET name = $3 WHERE guild_id = $1 AND name = $2',
                ctx.guild.id,
                name.lower(),
                new_name.lower()
            )

            if result == 'UPDATE 0':
                raise commands.BadArgument(f'Sound **{name}** does not exist.')

            await yes(ctx)

    @commands.command(aliases=['l'])
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
                if len(message) + len(line) > 2000:
                    await ctx.send(message)
                    message = ''
                message += line

        if message:
            await ctx.send(message)

    @commands.command(aliases=['s'])
    async def stop(self, ctx: commands.Context):
        """
        Stop playback of the current sound.
        """
        try:
            await self.playing.pop(ctx.guild.id)
        except KeyError:
            # nothing was playing
            pass

    @commands.command(aliases=['i'])
    async def info(self, ctx: commands.Context, name: str):
        """
        Get info about a sound.

        :param name: The sound to get info about.
        """
        async with self.bot.pool.acquire() as conn:
            sound = await conn.fetchval(
                'SELECT (played, stopped, source, uploader, upload_time) FROM sounds WHERE guild_id = $1 AND name = $2',
                ctx.guild.id,
                name.lower()
            )

        if sound is None:
            raise commands.BadArgument(f'Sound **{name}** does not exist.')

        played, stopped, source, uploader_id, upload_time = sound

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

        await ctx.send(embed=embed)

    @commands.command(aliases=['ra'])
    async def rand(self, ctx: commands.Context, *, args=None):
        """
        Play a random sound.

        :param args: The volume/speed of playback, in format v[XX%] s[SS%]. e.g. v50 s100 for 50% sound, 100% speed.
        """
        async with self.bot.pool.acquire() as conn:
            name = await conn.fetchval(
                'SELECT name FROM sounds WHERE guild_id = $1 ORDER BY RANDOM() LIMIT 1',
                ctx.guild.id
            )
        log.debug(f'Playing random sound {name}.')
        await ctx.invoke(self.play, name, args=args)

    @commands.command()
    async def last(self, ctx: commands.Context):
        """
        Play the last sound played.
        """
        try:
            name, args = self.last_played[ctx.guild.id]
        except KeyError:
            raise commands.CommandError('No sounds played yet.')

        await ctx.invoke(self.play, name, args=args)

    @commands.command()
    async def search(self, ctx: commands.Context, query: str):
        """
        Search for a sound.
        """

        async with self.bot.pool.acquire() as conn:
            results = await self._search(ctx.guild.id, query, conn)

        if not results:
            await ctx.send('No results found.')
        else:
            results = [record['name'] for record in results]
            response = f'Found {len(results)} result{"s" if len(results) != 1 else ""}.\n' + '\n'.join(results)
            await ctx.send(response)

    async def _search(self, guild_id, query, connection, threshold=0.1, limit=10):
        await connection.execute(f'SET pg_trgm.similarity_threshold = {threshold};')
        results = await connection.fetch(
            'SELECT name FROM sounds WHERE guild_id = $1 AND name % $2 ORDER BY similarity(name, $2) DESC LIMIT $3',
            guild_id,
            query,
            limit
        )

        return results


def setup(bot):
    bot.add_cog(SoundBoard(bot))
