import asyncio
import logging
from collections import OrderedDict

import discord
from discord.ext import commands

from ..soundbert import SoundBert
from .utils.reactions import yes

log = logging.getLogger(__name__)


class Clipboard(commands.Cog):
    def __init__(self, bot: SoundBert):
        self.bot = bot

        self.last_pasted = {}

    @commands.group(aliases=['cb'], invoke_without_command=True)
    async def clipboard(self, ctx: commands.Context):
        """
        A clipboard of text.
        """
        await ctx.invoke(self.list)

    @clipboard.command(aliases=['+', 'add', 'a', 'c'])
    async def copy(self, ctx: commands.Context, name: str, *, content: str = None):
        """
        Add a new clip to the clipboard.

        :param name: The name of the new clip.
        :param content: Content new clip. If omitted, command must be called in the comment of an attachment.
        """
        # Resolve content
        if content is None:
            try:
                content = ctx.message.attachment[0].url
            except (IndexError, KeyError):
                raise commands.BadArgument('Text content or attachment required.')

        async with self.bot.pool.acquire() as conn:
            async with conn.transaction():
                # Disallow duplicates
                exists = await conn.fetchval(
                    'SELECT EXISTS(SELECT 1 FROM clips WHERE guild_id = $1 AND name = $2)',
                    ctx.guild.id,
                    name.lower()
                )

                if exists:
                    raise commands.BadArgument(f'Clip named `{name}` already exists.')

                await conn.execute(
                    'INSERT INTO guilds(id) VALUES ($1) ON CONFLICT DO NOTHING',
                    ctx.guild.id
                )

                await conn.execute(
                    'INSERT INTO clips(guild_id, name, uploader, upload_time, content) VALUES ($1, $2, $3, $4, $5)',
                    ctx.guild.id,
                    name.lower(),
                    ctx.author.id,
                    ctx.message.created_at,
                    content
                )

                await yes(ctx)

    @clipboard.command(aliases=['!', 'p'])
    async def paste(self, ctx: commands.Context, name: str):
        """
        Paste a clip.

        :param name: The name of the clip to paste.
        """

        if not name:
            raise commands.BadArgument('Invalid clip name.')

        async with self.bot.pool.acquire() as conn:
            clip = await conn.fetchval(
                'SELECT content FROM clips WHERE guild_id = $1 AND name = $2',
                ctx.guild.id,
                name.lower()
            )

            if clip is None:
                results = await self._search(ctx.guild.id, name, conn)
                if len(results) > 0:
                    results = '\n'.join(result['name'] for result in results)
                    raise commands.BadArgument(f'Clip **{name}** does not exist. Did you mean:\n{results}')
                else:
                    raise commands.BadArgument(f'Clip **{name}** does not exist.')

            await conn.execute(
                'UPDATE clips SET pasted = pasted + 1 WHERE guild_id = $1 AND name = $2',
                ctx.guild.id,
                name.lower()
            )

        await ctx.send(clip)
        self.last_pasted[ctx.guild.id] = name

    @clipboard.command(aliases=['-', 'd', 'del'])
    async def delete(self, ctx: commands.Context, name: str):
        """
        Delete a clip.

        :param name: The name of the clip to delete.
        """
        async with self.bot.pool.acquire() as conn:
            result = await conn.execute(
                'DELETE FROM clips WHERE guild_id = $1 AND name = $2',
                ctx.guild.id,
                name.lower()
            )

            if result == 'DELETE 0':
                raise commands.BadArgument(f'Clip **{name}** does not exists.')

            await yes(ctx)

    @clipboard.command(aliases=['~', 're'])
    async def rename(self, ctx: commands.Context, name: str, new_name: str):
        """
        Rename a clip.

        :param name: The name of the clip to rename.
        :param new_name: The new name.
        """
        async with self.bot.pool.acquire() as conn:
            new_name_exists = await conn.execute(
                'SELECT EXISTS(SELECT 1 FROM clips WHERE guild_id = $1 and name = $2)',
                ctx.guild.id,
                new_name.lower()
            )

            if new_name_exists:
                raise commands.BadArgument(f'There is already a clip named **{name}**.')

            result = await conn.execute(
                'UPDATE clips SET name = $3 WHERE guild_id = $1 AND name = $2',
                ctx.guild.id,
                name.lower(),
                new_name.lower()
            )

            if result == 'UPDATE 0':
                raise commands.BadArgument(f'Clip **{name}** does not exists.')

            await yes(ctx)

    @clipboard.command(aliases=['l'])
    async def list(self, ctx: commands.Context):
        """
        List all the clips on the clipboard.
        """
        async with self.bot.pool.acquire() as conn:
            clips = await conn.fetch('SELECT name FROM clips WHERE guild_id = $1 ORDER BY name', ctx.guild.id)
        if len(clips) == 0:
            message = 'No clips yet.'
        else:
            split = OrderedDict()
            for clip in clips:
                name = clip['name']
                first = name[0].lower()
                if first not in 'abcdefghijklmnopqrstuvwxyz':
                    first = '#'
                if first not in split.keys():
                    split[first] = [name]
                else:
                    split[first].append(name)

            message = '**Clips**\n'
            for letter, clips_ in split.items():
                line = f'**`{letter}`**: {", ".join(clips_)}\n'
                if len(message) + len(line) > 2000:
                    await ctx.send(message)
                    message = ''
                message += line

        if message:
            await ctx.send(message)

    @clipboard.command(aliases=['i'])
    async def info(self, ctx: commands.Context, name: str):
        """
        Get info about a clip.

        :param name: The clip to get info about.
        """
        async with self.bot.pool.acquire() as conn:
            clip = await conn.fetchval(
                'SELECT (pasted, uploader, upload_time) FROM clips WHERE guild_id = $1 AND name = $2',
                ctx.guild.id,
                name.lower()
            )

        if clip is None:
            raise commands.BadArgument(f'Clip **{name}** does not exist.')

        pasted, uploader_id, upload_time = clip

        embed = discord.Embed()
        embed.title = name

        if uploader_id:
            uploader = self.bot.get_user(uploader_id) or (await self.bot.fetch_user(uploader_id))
            embed.set_author(name=uploader.name, icon_url=uploader.avatar_url)
            embed.add_field(name='Uploader', value=f'<@{uploader_id}>')
        if upload_time:
            embed.set_footer(text='Uploaded at')
            embed.timestamp = upload_time
        embed.add_field(name='Pasted', value=pasted)

        await ctx.send(embed=embed)

    @clipboard.command(aliases=['ra'])
    async def rand(self, ctx: commands.Context):
        """
        Paste a random clip.
        """
        async with self.bot.pool.acquire() as conn:
            name = await conn.fetchval(
                'SELECT name FROM clips WHERE guild_id = $1 ORDER BY RANDOM() LIMIT 1',
                ctx.guild.id
            )
        log.debug(f'Pasting random clip {name}.')
        await ctx.invoke(self.paste, name)

    @clipboard.command()
    async def last(self, ctx: commands.Context):
        """
        Paste the last clip pasted.
        """
        try:
            name = self.last[ctx.guild.id]
        except KeyError:
            raise commands.CommandError('No clips played yet.')

        await ctx.invoke(self.paste, name)

    @clipboard.command()
    async def search(self, ctx: commands.Context, query: str):
        """
        Search for a clip.
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
            'SELECT name FROM clips WHERE guild_id = $1 AND name % $2 ORDER BY similarity(name, $2) DESC LIMIT $3',
            guild_id,
            query,
            limit
        )

        return results


def setup(bot):
    bot.add_cog(Clipboard(bot))
