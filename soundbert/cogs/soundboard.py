import asyncio
import hashlib
import os
from collections import OrderedDict

import aiohttp
import discord
from discord import VoiceClient
from discord.ext import commands

from soundbert.utils.reactions import yes, no


class Sounds:
    def __init__(self, sound_dir, bot):
        self.sound_dir = sound_dir
        self.pool = bot.db_pool

        self.playing = {}

    # @commands.command()
    # async def test(self, ctx, *, sql):
    #     async with self.pool.acquire() as conn:
    #         result = await conn.fetchrow(sql)
    #     await ctx.send(str(dict(result)))

    @commands.command(
        aliases=['!', 'soundboard', 'soundbot', 'soundbert', 'sb']
    )
    async def play(self, ctx: commands.Context, name: str, *, args=None):
        """
        Play a sound.
        :param name: The sound to play.
        :param args: The volume/speed of playback, in format v[volume%] s[speed%]. e.g. v50 s100. Both are optional.
        """

        channel = None

        if len(ctx.message.mentions) == 1 and ctx.message.mentions_everyone is False:
            channel = ctx.message.mentions[0].voice.channel

        if channel is None:
            channel = ctx.author.voice.channel

        if channel is None:
            return

        # TODO: make these not hard-coded
        default_speed = 100
        default_volume = 50

        speed = None
        volume = None

        if args is not None:
            for arg in args.split():
                if speed is None and arg.startswith('s'):
                    try:
                        speed = int(arg[1:])
                        speed = max(speed, 50)
                        speed = min(speed, 200)
                    except ValueError:
                        speed = default_speed
                if volume is None and arg.startswith('v'):
                    try:
                        volume = int(arg[1:])
                    except ValueError:
                        volume = default_volume
        else:
            speed = default_speed
            volume = default_volume

        if speed is None:
            speed = default_speed
        if volume is None:
            volume = default_volume

        if name is None:
            return

        async with self.pool.acquire() as conn:
            sound = await conn.fetchrow('SELECT * FROM sounds WHERE name = $1;', name)

        filename = sound['filename']

        vclient: VoiceClient = ctx.guild.voice_client
        if vclient is not None:
            vclient.move_to(channel)
        else:
            vclient = await channel.connect()

        play = asyncio.Event()
        stop = asyncio.Event()
        self.playing[ctx.guild.id] = (name, play, stop)

        source = discord.FFmpegPCMAudio(f'{self.sound_dir}/{filename}',
                                        options=f'-filter:a "atempo={speed/100}"' if speed != default_speed else None)

        source = discord.PCMVolumeTransformer(source, volume=volume / 100)

        vclient.play(source=source, after=lambda error: play.set())

        await play.wait()
        await vclient.disconnect(force=True)
        stop.set()
        try:
            self.playing.pop(ctx.guild.id)
        except KeyError:
            pass

        async with self.pool.acquire() as conn:
            await conn.execute('UPDATE sounds SET played = played + 1 WHERE name = $1', name)

    @commands.command()
    async def add(self, ctx: commands.Context, name: str, link: str = None):
        """
        Add a new sound.
        :param name: The name of the sound to add.
        :param link: The download link to the sound. Can be omitted if command invocation has an attachment.
        """

        # Disallow duplicate names
        async with self.pool.acquire() as conn:
            exists = await conn.fetchval('SELECT EXISTS(SELECT 1 FROM sounds WHERE name = $1);', name)

        if exists:
            await no(ctx)
            await ctx.send(f'Sound named **{name}** already exists.')
            return

        # Resolve download url.
        if link is None:
            try:
                link = ctx.message.attachements[0]['url']
            except (IndexError, KeyError):
                await no(ctx)
                await ctx.send('Download link or file attachment required.')
                return

        # Download file
        with ctx.typing():
            async with aiohttp.ClientSession() as session:
                async with session.get(link) as resp:
                    if resp.status == 200:

                        # Write response to temporary file and moves it to the /sounds directory when done.
                        # Filename = blake2 hash of file
                        hash = hashlib.blake2b()
                        with open(f'{os.getcwd()}/tempsound', 'wb') as f:
                            while True:
                                chunk = await resp.content.read(1024)
                                if not chunk:
                                    break
                                hash.update(chunk)
                                f.write(chunk)

                        filename = hash.hexdigest().upper()

                        try:
                            os.rename(f'{os.getcwd()}/tempsound', f'{self.sound_dir}/{filename}')

                            async with self.pool.acquire() as conn:
                                await conn.execute('INSERT INTO sounds(name, filename) VALUES ($1, $2);',
                                                   name, filename)
                            await yes(ctx)
                        except FileExistsError:
                            await no(ctx)
                            await ctx.send(f'Sound already exists.')

                    else:
                        await no(ctx)
                        await ctx.send(f'Error while downloading: {resp.status}: {resp.reason}.')
                    await resp.release()

    @commands.command(aliases=['del'])
    async def remove(self, ctx: commands.Context, name: str):
        """
        Remove a sound.
        :param name: The sound to remove.
        """

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                sound = await conn.fetchrow('SELECT (name, filename) FROM sounds WHERE name = $1;', name)
                if sound is None:
                    await ctx.send(f'Sound **{name}** does not exist.')
                    await no(ctx)
                    return
                else:
                    await conn.execute('DELETE FROM sounds WHERE name = $1', sound['name'])

        filename = sound['filename']
        os.remove(f'{self.sound_dir}/{filename}')
        # await ctx.send(f'Removed **{name}**.')
        await yes(ctx)

    @commands.command()
    async def rename(self, ctx: commands.Context, name: str, new_name: str):
        """
        Rename a sound.
        :param name: The sound to rename.
        :param new_name: The new name of the sound.
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                sound = await conn.fetchrow('SELECT (id, name, filename) FROM sounds WHERE name = $1;', name)
                if sound is None:
                    await ctx.send(f'Sound **{name}** does not exist.')
                    await no(ctx)
                    return
                else:
                    await conn.execute('UPDATE sounds SET name = $2 WHERE name = $1', name, new_name)

        await yes(ctx)
        # await ctx.send(f'**{name}** renamed to **{new_name}**.')

    @commands.command()
    async def list(self, ctx: commands.Context):
        """
        List all sounds.
        """
        async with self.pool.acquire() as conn:
            sounds = await conn.fetch('SELECT * FROM sounds ORDER BY name;')
        if len(sounds) == 0:
            message = 'No sounds yet. Add one with `+<name> <link>`!'
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
        name, play, stop = self.playing.pop(ctx.guild.id)
        play.set()
        await stop.wait()
        async with self.pool.acquire() as conn:
            await conn.execute('UPDATE sounds SET played = played + 1 WHERE name = $1', name)

    @commands.command()
    async def stat(self, ctx: commands.Context, name: str):
        """
        Get stats of a sound.
        :param name: The sound to get stats for.
        """
        async with self.pool.acquire() as conn:
            sound = await conn.fetchrow('SELECT * FROM sounds WHERE name = $1;', name)

        if sound is None:
            await ctx.send(f'Sound **{name}** does not exist.')
            await no(ctx)
            return

        played = sound['played']
        stopped = sound['stopped']

        resp = f'**{name}** stats:\nPlayed {played} times.\nStopped {stopped} times.'
        await ctx.send(resp)

    @commands.command()
    async def rand(self, ctx: commands.Context, *, args=None):
        """
        Play a random sound.
        :param args: The volume/speed of playback, in format v[volume%] s[speed%]. e.g. v50 s100. Both are optional.
        """
        async with self.pool.acquire() as conn:
            name = await conn.fetchval('SELECT name FROM sounds ORDER BY RANDOM() LIMIT 1;')
        await ctx.invoke(self.play, name, args=args)
