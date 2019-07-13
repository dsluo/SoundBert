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

from .utils.converters import DurationConverter
from .utils.reactions import no, yes
from ..soundbert import SoundBert

log = logging.getLogger(__name__)


class SoundBoard(commands.Cog):
    def __init__(self, bot: 'SoundBert'):
        self.sound_path = Path(bot.config['soundboard']['path'])
        self.bot = bot

        self.playing = {}
        self.muted = {}
        self.last_played = {}

        if not self.sound_path.is_dir():
            self.sound_path.mkdir()

    @commands.command(aliases=['!', 'p'])
    async def play(self, ctx: commands.Context, name: str, *, args=None):
        """
        Play a sound.

        :param name: The name of the sound to play.
        :param args: The volume/speed of playback, in format v[XX%] s[SS%]. e.g. v50 s100.
        """
        if ctx.guild.id in self.muted and name in self.muted[ctx.guild.id]:
            await ctx.message.add_reaction('\N{SPEAKER WITH CANCELLATION STROKE}')
            return
            # raise commands.CommandError('Sound is muted.')

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

                        seek = f'{hours}:{mins:02}:{secs:02}'
                    except ValueError:
                        raise commands.BadArgument(f'Could not parse `{args}`.')

        if volume is None:
            volume = 100

        try:
            channel = ctx.author.voice.channel
        except AttributeError:
            raise commands.CommandError('No target channel.')

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
            return name

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
                name
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
                        raise FileNotFoundError("Couldn't find postprocessed file")

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
                    raise commands.BadArgument('Error while creating guild directory.')

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
                    'INSERT INTO sounds(guild_id, name, filename, uploader, source) VALUES ($1, $2, $3, $4, $5)',
                    ctx.guild.id,
                    name.lower(),
                    filename,
                    ctx.author.id,
                    link
                )
                await yes(ctx)

    @commands.command(aliases=['-', 'd', 'del'])
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

    @commands.command(aliases=['~', 'r'])
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
                if len(message) + len(line) > 2000:
                    await ctx.send(message)
                    message = ''
                message += line

        if message:
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
    async def info(self, ctx: commands.Context, name: str):
        """
        Get info about a sound.

        :param name: The sound to get info about.
        """
        async with self.bot.pool.acquire() as conn:
            sound = await conn.fetchval(
                'SELECT (played, stopped, source, uploader) FROM sounds WHERE guild_id = $1 AND name = $2',
                ctx.guild.id,
                name.lower()
            )

        if sound is None:
            raise commands.BadArgument(f'Sound **{name}** does not exist.')

        played, stopped, source, uploader_id = sound

        embed = discord.Embed()
        embed.title = name

        if uploader_id:
            uploader = self.bot.get_user(uploader_id) or (await self.bot.fetch_user(uploader_id))
            embed.set_author(name=uploader.name, icon_url=uploader.avatar_url)
            embed.add_field(name='Uploader', value=f'<@{uploader_id}>')
        if source:
            embed.add_field(name='Source', value=source)
        embed.add_field(name='Played', value=played)
        embed.add_field(name='Stopped', value=stopped)

        await ctx.send(embed=embed)

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
        log.debug(f'Playing random sound {name}.')
        await ctx.invoke(self.play, name, args=args)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def id(self, ctx: commands.Context, name, guild_id=None):
        async with self.bot.pool.acquire() as conn:
            filename = await conn.fetchval(
                'SELECT filename FROM sounds WHERE guild_id = $1 AND name = $2',
                guild_id or ctx.guild.id,
                name.lower()
            )

        await ctx.send(str(filename))

    async def mute_sound(self, guild_id, name, seconds):
        if guild_id not in self.muted:
            self.muted[guild_id] = [name]
        else:
            self.muted[guild_id].append(name)

        await asyncio.sleep(seconds)

        await self.unmute_sound(guild_id, name)

    async def unmute_sound(self, guild_id, name):
        self.muted[guild_id].remove(name)
        if self.muted[guild_id]:
            del self.muted[guild_id]

    @commands.command()
    async def mute(self, ctx: commands.Context, name, *, duration: DurationConverter):
        """
        Mute the specified sound for a certain amount of time.
        :param name: The name of the sound to mute.
        :param duration: How long to mute it.
        """
        self.bot.loop.create_task(self.mute_sound(ctx.guild.id, name, duration.total_seconds()))
        await yes(ctx)

    @commands.command()
    async def unmute(self, ctx: commands.Context, name):
        """
        Unmute the specified sound.
        :param name: The name of the sound to unmute.
        """
        await self.unmute_sound(ctx.guild.id, name)
        await yes(ctx)

    @commands.command(name='last')
    async def last_played(self, ctx: commands.Context):
        """
        Play the last sound played.
        """
        try:
            name, args = self.last_played[ctx.guild.id]
        except KeyError:
            await no(ctx)
            return

        await ctx.invoke(self.play, name, args=args)


def setup(bot):
    bot.add_cog(SoundBoard(bot))
