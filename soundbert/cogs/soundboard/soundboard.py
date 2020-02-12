import asyncio
import logging
import shutil
import tempfile
from pathlib import Path

import aiohttp
import asyncpg
import discord
import youtube_dl
from discord import VoiceClient
from discord.ext import commands
from sqlalchemy import and_, select, func, exists

from . import exceptions
from .checks import is_soundmaster, is_soundplayer
from ..utils.humantime import humanduration, TimeUnits
from ..utils.paginator import DictionaryPaginator
from ..utils.pluralize import pluralize
from ..utils.reactions import ok
from ...database import sounds, sound_names
from ...soundbert import SoundBert

log = logging.getLogger(__name__)


# noinspection PyIncorrectDocstring
class SoundBoard(commands.Cog):
    def __init__(self, bot: 'SoundBert'):
        self.sound_path = Path(bot.config.sound_path)
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

        sound_id = await self.bot.db.fetch_val(
                select([sounds.c.id])
                    .select_from(sounds.join(sound_names))
                    .where(and_(
                        sound_names.c.guild_id == ctx.guild.id,
                        sound_names.c.name == name
                ))
        )

        if sound_id is None:
            records = await self._search(ctx.guild.id, name)
            if len(records) > 0:
                records = '\n'.join(record[sound_names.c.name] for record in records)
                raise exceptions.SoundDoesNotExist(name, records)
            else:
                raise exceptions.SoundDoesNotExist(name)

        file = self.sound_path / str(ctx.guild.id) / name

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
                f'Playing sound {name} ({sound_id}) in #{channel.name} ({channel.id}) of guild {ctx.guild.name} ({ctx.guild.id}).'
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
            return sound_id

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
                    .where(sounds.c.id == sound_id)
        )

        log.debug('Starting playback.')
        vclient.play(source=source, after=wrapper)

    @commands.command(name='import', hidden=True)
    # @commands.check(is_soundmaster)
    @commands.is_owner()
    async def import_(self, ctx: commands.Context, source: str = None):
        """
        Imports sounds from an archive. Sounds are named the name of the file in the archive.
        Supports .zip, .tar, .tar.gz, .tgz, .tar.bz2, .tbz2, .tar.xz, and .txz archives.

        :param source: Download link to an archive. Can be omitted if archive is uploaded as an attachment.
        """

        if source is None:
            try:
                source = ctx.message.attachments[0].url
            except (IndexError, KeyError):
                raise exceptions.NoDownload()

        with tempfile.NamedTemporaryFile('wb+') as f, tempfile.TemporaryDirectory() as d:

            async with aiohttp.ClientSession() as session:
                async with session.get(source) as resp:
                    filename = resp.url.name

                    # this might block but i don't care.
                    while True:
                        chunk = await resp.content.read(1 << 20)  # 1 MB
                        if not chunk:
                            break
                        f.write(chunk)

            f.seek(0)  # this probably doesn't matter

            format = None
            for fmt in shutil.get_unpack_formats():
                for extension in fmt[1]:
                    if filename.endswith(extension):
                        format = fmt[0]
                        break
                # this weird stuff is because python has no syntax for
                # breaking out of multiple loops.
                else:
                    continue
                break

            shutil.unpack_archive(f.name, d, format=format)
            f.close()

            succeeded = []
            failed = []
            for path in Path(d).glob('**/*'):
                if not path.is_file():
                    continue
                try:
                    await self._add(ctx, path.name, source, path, unlink=False)
                    succeeded.append(path.name)
                except FileExistsError:
                    failed.append(path.name)
            msg = f'{len(succeeded)} imported. {len(failed)} failed.'
            if failed:
                msg += '\nFailed imports:\n'
                msg += '\n'.join(failed)
            await ctx.send(msg)

    @commands.command()
    @commands.check(is_soundmaster)
    async def add(self, ctx: commands.Context, name: str, source: str = None):
        """
        Add a new sound to the soundboard.

        :param name: The name of the new sound.
        :param source: Download link to new sound. Can be omitted if sound is uploaded as an attachment.
        """
        # Resolve download url.

        if len(name) > 255:
            raise exceptions.NameTooLong()

        if source is None:
            try:
                source = ctx.message.attachments[0].url
            except (IndexError, KeyError):
                raise exceptions.NoDownload()

        # Disallow duplicate names
        sound_exists = await self.bot.db.fetch_val(
                select([
                    exists([1])
                        .where(and_(
                            sound_names.c.guild_id == ctx.guild.id,
                            sound_names.c.name == name
                    ))
                ])
        )

        if sound_exists:
            raise exceptions.SoundExists(name)

        # Download file
        await ctx.trigger_typing()

        def download_sound(url):
            log.debug(f'Downloading from {url}.')
            # it is impossible to pipe directly from youtube-dl's output because it does not provide an API for it
            # https://github.com/ytdl-org/youtube-dl/blob/fffc618c519d10a7335eb5b06ab13d56ecea8561/youtube_dl/utils.py#L2030-L2059
            options = {
                'format':            'webm[abr>0]/bestaudio/best',
                'restrictfilenames': True,
                'default_search':    'error',
                'logger':            log
            }
            yt = youtube_dl.YoutubeDL(options)
            info = yt.extract_info(url)

            filename = yt.prepare_filename(info)

            return info, Path(filename)

        try:
            info, file = await self.bot.loop.run_in_executor(None, download_sound, source)
        except youtube_dl.DownloadError:
            raise exceptions.DownloadError()

        length = info.get('duration')

        try:
            await self._add(ctx, name, source, file, length=length, unlink=True)
        except FileExistsError:
            raise exceptions.SoundExists(name)

        await ok(ctx)

    async def _add(self, ctx: commands.Context, name: str, source: str, file: Path, length=None, unlink=False):
        if not length:
            length = await SoundBoard.get_length(file)

        server_dir = self.sound_path / str(ctx.guild.id)

        if not server_dir.exists():
            server_dir.mkdir()

        if (server_dir / name).exists():
            if unlink:
                file.unlink()
            raise FileExistsError

        # allows this to work on docker
        shutil.move(str(file), str(server_dir / name))

        async with self.bot.db.transaction():
            sound_id = await self.bot.db.fetch_val(
                    sounds.insert()
                        .returning(sounds.c.id)
                        .values(
                            uploader=ctx.author.id,
                            source=source,
                            length=length
                    )
            )

            await self.bot.db.fetch_val(
                    sound_names.insert()
                        .values(
                            sound_id=sound_id,
                            guild_id=ctx.guild.id,
                            name=name
                    )
            )

    @commands.command()
    @commands.check(is_soundmaster)
    async def alias(self, ctx: commands.Context, name: str, alias: str):
        """
        Allows sounds to be played by a different name.

        :param name: The sound to alias.
        :param alias: The alias to assign
        """

        if len(alias) > 255:
            raise exceptions.NameTooLong()

        async with self.bot.db.transaction():
            target_sound_name = await self.bot.db.fetch_one(
                    select([sound_names.c.sound_id, sound_names.c.is_alias])
                        .where(and_(
                            sound_names.c.guild_id == ctx.guild.id,
                            sound_names.c.name == name
                    ))
            )

            if target_sound_name is None:
                raise exceptions.SoundDoesNotExist(name)

            sound_id = target_sound_name[sound_names.c.sound_id]
            is_already_alias = target_sound_name[sound_names.c.is_alias]

            if is_already_alias:
                raise exceptions.AliasTargetIsAlias()

            try:
                await self.bot.db.execute(
                        sound_names.insert()
                            .values(
                                sound_id=sound_id,
                                guild_id=ctx.guild.id,
                                name=alias,
                                is_alias=True
                        )
                )

                link = self.sound_path / str(ctx.guild.id) / alias
                link.symlink_to(name)
            except asyncpg.UniqueViolationError:
                raise exceptions.SoundExists(alias)
            else:
                await ok(ctx)

    @commands.command(aliases=['del', 'rm'])
    @commands.check(is_soundmaster)
    async def delete(self, ctx: commands.Context, name: str):
        """
        Delete a sound or an alias.

        :param name: The name of the sound or alias to delete.
        """
        async with self.bot.db.transaction():
            sound_with_name = await self.bot.db.fetch_one(
                    select([sound_names.c.id, sound_names.c.sound_id, sound_names.c.is_alias])
                        .where(and_(
                            sound_names.c.guild_id == ctx.guild.id,
                            sound_names.c.name == name
                    ))
            )

            if sound_with_name is None:
                raise exceptions.SoundDoesNotExist(name)

            name_id = sound_with_name[sound_names.c.id]
            sound_id = sound_with_name[sound_names.c.sound_id]
            is_alias = sound_with_name[sound_names.c.is_alias]

            if is_alias:
                # if alias, just delete the alias.
                await self.bot.db.execute(sound_names.delete().where(sound_names.c.id == name_id))
            else:
                # if not alias, delete the sound and CASCADE will take care of the names and aliases.
                await self.bot.db.execute(sounds.delete().where(sounds.c.id == sound_id))

            # aliases are symbolic links, so this will still work
            file = self.sound_path / str(ctx.guild.id) / name
            file.unlink()
            await ok(ctx)

    @commands.command(aliases=['mv'])
    @commands.check(is_soundmaster)
    async def rename(self, ctx: commands.Context, name: str, new_name: str):
        """
        Rename a sound or alias.

        :param name: The name of the sound or alias to rename.
        :param new_name: The new name.
        """

        if len(new_name) > 255:
            raise exceptions.NameTooLong()

        async with self.bot.db.transaction():
            try:
                sound_exists = await self.bot.db.fetch_val(
                        sound_names.update()
                            .returning(sound_names.c.id)
                            .values(name=new_name)
                            .where(and_(
                                sound_names.c.guild_id == ctx.guild.id,
                                sound_names.c.name == name
                        ))
                )
                if sound_exists is None:
                    raise exceptions.SoundDoesNotExist(name)
                file = self.sound_path / str(ctx.guild.id) / name
                renamed = file.with_name(new_name)
                shutil.move(str(file), str(renamed))
            except asyncpg.UniqueViolationError:
                raise exceptions.SoundExists(new_name)
            else:
                await ok(ctx)

    @commands.command(aliases=['ls'])
    @commands.check(is_soundplayer)
    async def list(self, ctx: commands.Context):
        """
        List all the sounds on the soundboard.
        """

        all_sounds = await self.bot.db.fetch_all(
                select([sound_names.c.name])
                    .where(and_(
                        sound_names.c.guild_id == ctx.guild.id,
                        ~sound_names.c.is_alias
                ))
                    .order_by(sound_names.c.name)
        )

        if len(all_sounds) == 0:
            raise exceptions.NoSounds()

        all_sounds = [sound[sound_names.c.name] for sound in all_sounds]
        paginator = DictionaryPaginator(ctx, items=all_sounds, header='**Sounds**')
        await paginator.paginate()

    @commands.command()
    @commands.check(is_soundplayer)
    async def stop(self, ctx: commands.Context):
        """
        Stop playback of the current sound.
        """

        try:
            id = await self.playing.pop(ctx.guild.id)
            await self.bot.db.execute(
                    sounds.update()
                        .values(stopped=sounds.c.stopped + 1)
                        .where(sounds.c.id == id)
            )
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
                        sound_names.c.name == name
                ))
        )

        if sound is None:
            raise exceptions.SoundDoesNotExist(name)

        names = [
            record[sound_names.c.name]
            for record in await self.bot.db.fetch_all(
                    select([sound_names.c.name])
                        .where(sound_names.c.sound_id == sound[sounds.c.id])
                        .order_by(sound_names.c.is_alias, sound_names.c.name)
            )
        ]

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
                    .where(
                        and_(
                                sound_names.c.guild_id == ctx.guild.id,
                                ~sound_names.c.is_alias
                        ))
                    .offset(
                        func.floor(
                                func.random() *
                                select([func.count()])
                                .select_from(sound_names)
                                .where(sound_names.c.guild_id == ctx.guild.id)))
                    .limit(1)
        )
        log.debug(f'Playing random sound {name}.')
        await ctx.invoke(self.play, name, args=args)

    @commands.command(aliases=['find'])
    @commands.check(is_soundplayer)
    async def search(self, ctx: commands.Context, query: str):
        """
        Search for a sound.
        """

        records = await self._search(ctx.guild.id, query)

        if not records:
            await ctx.send('No results found.')
        else:
            results = [
                f'*{record[sound_names.c.name]}*' if record[sound_names.c.is_alias] else record[sound_names.c.name]
                for record in records
            ]
            header = f'Found {len(results)} {pluralize(len(results), "result")}.'

            has_aliases = sum(1 for record in records if record[sound_names.c.is_alias]) > 0
            if has_aliases:
                header += ' Aliases are *italicized*.\n'
            else:
                header += '\n'

            response = header + '\n'.join(results)
            await ctx.send(response)

    async def _search(self, guild_id, query, alias=None, limit=10):
        """
        Search for a sound.

        :param guild_id: The guild ID.
        :param query: The sound to search.
        :param alias: True for only aliases, False for no aliases, None for any.
        :param limit: Maximum number of results to produce.
        :return:
        """

        whereclause = and_(
                # The first % escapes the second % here.
                sound_names.c.name.op('%%')(query),
                sound_names.c.guild_id == guild_id
        )

        if alias is not None:
            whereclause.append(
                    sound_names.c.is_alias == alias
            )

        similarity = func.similarity(sound_names.c.name, query).label('similarity')

        return await self.bot.db.fetch_all(
                select([
                    sound_names.c.name,
                    sound_names.c.is_alias,
                    # similarity
                ])
                    .where(whereclause)
                    .order_by(similarity.desc())
                    .limit(limit)
        )
