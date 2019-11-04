import discord
from discord.ext import commands
from sqlalchemy import select

from ...database import guilds
from . import exceptions


async def is_soundmaster(ctx: commands.Context):
    if await ctx.bot.is_owner(ctx.author):
        return True
    if ctx.guild.owner == ctx.author:
        return True
    if ctx.author.guild_permissions.manage_guild:
        return True

    soundmaster = await ctx.bot.db.fetch_val(
        select([guilds.c.soundmaster])
            .where(guilds.c.id == ctx.guild.id)
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

    soundplayer = await ctx.bot.db.fetch_val(
        select([guilds.c.soundplayer])
            .where(guilds.c.id == ctx.guild.id)
    )

    if soundplayer is None:
        return True
    role = discord.utils.get(ctx.author.roles, id=soundplayer)
    if role is not None:
        return True

    soundplayer = ctx.guild.get_role(soundplayer)
    raise exceptions.NotSoundplayer(soundplayer)
