import discord
from discord.ext import commands
from sqlalchemy import select

from ..database import guilds
from .utils.reactions import yes
from ..soundbert import SoundBert


async def is_botmaster(ctx: commands.Context):
    if await ctx.bot.is_owner(ctx.author):
        return True
    if ctx.guild.owner == ctx.author:
        return True
    if ctx.author.guild_permissions.manage_guild:
        return True
    raise commands.CommandError(
        'You need to be the server owner or have manage guild permissions to run this command.'
    )


class Settings(commands.Cog):
    def __init__(self, bot: SoundBert):
        self.bot = bot

    @commands.group(invoke_without_command=True)
    async def settings(self, ctx: commands.Context):
        """
        Set bot server settings. Only the server owner or users with manage guild permissions can change settings.

        Use !settings <setting> <value> to change a setting's value.
        """

        settings = await self.bot.db.fetch_one(
            select([guilds.c.prefix, guilds.c.soundmaster, guilds.c.soundplayer])
                .where(guilds.c.id == ctx.guild.id)
        )

        embed = discord.Embed()
        embed.title = 'Settings'

        prefix = settings[guilds.c.prefix]
        soundmaster = settings[guilds.c.soundmaster]
        soundplayer = settings[guilds.c.soundplayer]

        embed.add_field(name='Prefix', value=prefix or self.bot.config['bot']['default_prefix'])
        embed.add_field(
            name='Sound Master Role',
            value=ctx.guild.get_role(soundmaster).mention if soundmaster else '@everyone'
        )
        embed.add_field(
            name='Sound Player Role',
            value=ctx.guild.get_role(soundplayer).mention if soundplayer else '@everyone'
        )

        await ctx.send(embed=embed)

    @settings.command()
    @commands.check(is_botmaster)
    async def prefix(self, ctx: commands.Context, prefix: str):
        """
        Set the prefix for this server (the symbol that specifies that a message is a command,
        e.g. !play -> -play).

        :param prefix: The new prefix
        """
        if len(prefix) > 20:
            raise commands.BadArgument('Prefix must be 20 characters or less.')

        await self.bot.db.execute(
            guilds.update()
                .where(guilds.c.id == ctx.guild.id)
                .values(prefix=prefix)
        )
        await yes(ctx)

    @settings.command()
    @commands.check(is_botmaster)
    async def soundmaster(self, ctx: commands.Context, role: discord.Role):
        """
        Set the role that can add/remove sounds. By default anyone can add/remove sounds.
        Soundmasters can always play sounds.

        :param role: The role to make master of sounds.
        """

        await self.bot.db.execute(
            guilds.update()
                .where(guilds.c.id == ctx.guild.id)
                .values(soundmaster=role.id)
        )
        await yes(ctx)

    @settings.command()
    @commands.check(is_botmaster)
    async def soundplayer(self, ctx: commands.Context, role: discord.Role):
        """
        Set the role that allows playing of sounds. By default anyone can play sounds.

        :param role: The role to make player of sounds.
        """

        await self.bot.db.execute(
            guilds.update()
                .where(guilds.c.id == ctx.guild.id)
                .values(soundplayer=role.id)
        )
        await yes(ctx)


def setup(bot):
    bot.add_cog(Settings(bot))
