import discord
from discord.ext import commands

from . import exceptions


async def is_soundmaster(ctx: commands.Context):
    if await ctx.bot.is_owner(ctx.author):
        return True
    if ctx.guild.owner == ctx.author:
        return True
    if ctx.author.guild_permissions.manage_guild:
        return True

    async with ctx.bot.pool.acquire() as conn:
        soundmaster = await conn.fetchval(
            'SELECT soundmaster FROM guilds WHERE id = $1',
            ctx.guild.id
        )

    if soundmaster is None:
        return True
    role = discord.utils.get(ctx.author.roles, id=soundmaster)
    if role is not None:
        return True

    soundmaster = ctx.guild.get_role(soundmaster)
    raise exceptions.NotSoundmaster(soundmaster)


async def is_soundplayer(ctx: commands.Context):
    if await is_soundmaster(ctx):
        return True

    async with ctx.bot.pool.acquire() as conn:
        soundplayer = await conn.fetchval(
            'SELECT soundplayer FROM guilds WHERE id = $1',
            ctx.guild.id
        )

    if soundplayer is None:
        return True
    role = discord.utils.get(ctx.author.roles, id=soundplayer)
    if role is not None:
        return True

    soundplayer = ctx.guild.get_role(soundplayer)
    raise exceptions.NotSoundplayer(soundplayer)