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
from sqlalchemy import and_, select, func, exists, true, column

from soundbert.database import sounds, sound_names
from . import exceptions
from .checks import is_soundmaster, is_soundplayer
from ..utils.humantime import humanduration, TimeUnits
from ..utils.reactions import yes
from ...soundbert import SoundBert

log = logging.getLogger(__name__)


# noinspection PyIncorrectDocstring
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

        sound = await self.bot.db.fetch_one(
                select([sounds.c.filename, sounds.c.id])
                    .select_from(sounds.join(sound_names))
                    .where(and_(
                        sound_names.c.guild_id == ctx.guild.id,
                        sound_names.c.name == name.lower()
                    ))
        )

        if sound is None:
            results = await self._search(ctx.guild.id, name)
            if len(results) > 0:
                results = '\n'.join(results)
                raise exceptions.SoundDoesNotExist(name, results)
            else:
                raise exceptions.SoundDoesNotExist(name)

        filename = sound[sounds.c.filename]
        id = sound[sounds.c.id]

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

            await self.bot.db.execute(
                    sounds.update()
                        .values(stopped=sounds.c.stopped + 1)
                        .where(and_(
                            sounds.c.id == sound_names.c.id,
                            sound_names.c.guild_id == ctx.guild.id,
                            sound_names.c.name == name.lower())
                    )
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

        await self.bot.db.execute(
                sounds.update()
                    .values(played=sounds.c.played + 1)
                    .where(and_(
                        sound_names.c.guild_id == ctx.guild.id,
                        sound_names.c.name == name.lower()
                ))
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

        # Disallow duplicate names
        sound_exists = await self.bot.db.fetch_val(
                select([
                    exists([1])
                        .where(and_(
                            sound_names.c.guild_id == ctx.guild.id,
                            sound_names.c.name == name.lower()
                    ))
                ])
        )

        if sound_exists:
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

        async with self.bot.db.transaction():
            sound_id = await self.bot.db.fetch_val(
                    sounds.insert()
                        .returning(sounds.c.id)
                        .values(
                            filename=file.name,
                            uploader=ctx.author.id,
                            source=link,
                            upload_time=ctx.message.created_at,
                            length=length
                    )
            )

            await self.bot.db.fetch_val(
                    sound_names.insert()
                        .values(
                            sound_id=sound_id,
                            guild_id=ctx.guild.id,
                            name=name.lower()
                    )
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
        try:
            sound_exists = await self.bot.db.fetch_val(
                    sound_names.insert()
                        .returning(sound_names.c.sound_id)
                        .from_select(
                            [sound_names.c.sound_id, sound_names.c.guild_id, sound_names.c.name,
                             sound_names.c.is_alias],
                            select([sound_names.c.sound_id, sound_names.c.guild_id, column(alias), true()])
                                .where(and_(
                                    sound_names.c.guild_id == ctx.guild.id,
                                    sound_names.c.name == name.lower()))
                    )
            )

            if sound_exists is not None:
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
        filename = await self.bot.db.fetch_val(
                select([sounds.c.filename])
                    .select_from(sounds.join(sound_names))
                    .where(and_(
                        sound_names.c.guild_id == ctx.guild.id,
                        sound_names.c.name == name.lower()
                ))
        )
        if filename is None:
            raise exceptions.SoundDoesNotExist(name)
        else:
            await self.bot.db.execute(
                    sounds.delete()
                        .where(and_(
                            sound_names.c.guild_id == ctx.guild.id,
                            filename == filename,
                            sound_names.c.sound_id == sounds.c.id
                    ))
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
        try:
            sound_exists = await self.bot.db.fetch_val(
                    sound_names.update()
                        .returning(sound_names.c.id)
                        .values(name=name.lower())
                        .where(and_(
                            sound_names.c.guild_id == ctx.guild.id,
                            sound_names.c.name == name.lower()
                    ))
            )
            if sound_exists is not None:
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

        sounds = await self.bot.db.fetch_all(
                select([sound_names.c.name])
                    .where(and_(
                        sound_names.c.guild_id == ctx.guild.id,
                        ~sound_names.c.is_alias
                ))
                    .order_by(sound_names.c.name)
        )

        if len(sounds) == 0:
            message = 'No sounds yet.'
        else:
            split = OrderedDict()
            for sound in sounds:
                name = sound[sound_names.c.name]
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

        sound = await self.bot.db.fetch_one(
                sounds.join(sound_names)
                    .select()
                    .where(and_(
                        sound_names.c.guild_id == ctx.guild.id,
                        sound_names.c.name == name.lower()
                ))
        )

        if sound is None:
            raise exceptions.SoundDoesNotExist(name)

        names = await self.bot.db.fetch_all(
                select([sound_names.c.name])
                    .where(sound_names.c.sound_id == sound[sounds.c.id])
                    .order_by(sound_names.c.is_alias, sound_names.c.name)
        )

        name, *aliases = names

        embed = discord.Embed()
        embed.title = name

        if sound[sounds.c.uploader]:
            uploader = self.bot.get_user(sound[sounds.c.uploader]) \
                       or (await self.bot.fetch_user(sound[sounds.c.uploader]))
            embed.set_author(name=uploader.name, icon_url=uploader.avatar_url)
            embed.add_field(name='Uploader', value=f'<@{sound[sounds.c.uploader]}>')
        if sound[sounds.c.upload_time]:
            embed.set_footer(text='Uploaded at')
            embed.timestamp = sound[sounds.c.upload_time]
        if sound[sounds.c.source]:
            embed.add_field(name='Source', value=sound[sounds.c.source])
        embed.add_field(name='Played', value=sound[sounds.c.played])
        embed.add_field(name='Stopped', value=sound[sounds.c.stopped])
        embed.add_field(name='Length', value=humanduration(sound[sounds.c.length], TimeUnits.MILLISECONDS))
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

        name = await self.bot.db.fetch_val(
                select([sound_names.c.name])
                    .where(and_(
                        sound_names.c.guild_id == ctx.guild.id,
                        ~sound_names.c.is_alias
                ))
                    .order_by(func.random())
                    .limit()
        )
        log.debug(f'Playing random sound {name}.')
        await ctx.invoke(self.play, name, args=args)

    @commands.command(aliases=['find'])
    @commands.check(is_soundplayer)
    async def search(self, ctx: commands.Context, query: str):
        """
        Search for a sound.
        """

        results = await self._search(ctx.guild.id, query)

        if not results:
            await ctx.send('No results found.')
        else:
            response = f'Found {len(results)} result{"s" if len(results) != 1 else ""}.\n' + '\n'.join(results)
            await ctx.send(response)

    async def _search(self, guild_id, query, alias=None, threshold=0.1, limit=10):
        """
        Search for a sound.

        :param guild_id: The guild ID.
        :param query: The sound to search.
        :param alias: True for only aliases, False for no aliases, None for any.
        :param threshold: The similarity threshold.
        :param limit: Maximum number of results to produce.
        :return:
        """

        await self.bot.db.execute(f'SET pg_trgm.similarity_threshold = {threshold};')

        if alias is None:
            whereclause = and_(
                    sound_names.c.guild_id == guild_id,
                    sound_names.c.name.op('%')(query)
            )
        else:
            whereclause = and_(
                    sound_names.c.guild_id == guild_id,
                    sound_names.c.name.op('%')(query),
                    sound_names.c.is_alias == alias
            )

        results = await self.bot.db.fetch_all(
                select([sound_names.c.name])
                .where(whereclause)
                .order_by(func.similarity(sound_names.c.name, query).desc())
                .limit(limit)
        )

        results = [record['name'] for record in results]

        return results
