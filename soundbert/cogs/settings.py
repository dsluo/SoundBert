import discord
from discord.ext import commands

from .utils.reactions import yes
from ..soundbert import SoundBert


async def is_botmaster(ctx: commands.Context):
    if ctx.bot.is_owner(ctx.author):
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

        async with self.bot.pool.acquire() as conn:
            settings = await conn.fetchrow(
                'SELECT (prefix, soundmaster, soundplayer) FROM guilds WHERE id = $1',
                ctx.guild.id
            )

        embed = discord.Embed()
        embed.title = 'Settings'

        prefix, soundmaster, soundplayer = settings['row']

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

        async with self.bot.pool.acquire() as conn:
            await conn.execute(
                'UPDATE guilds SET prefix = $1 WHERE id = $2',
                prefix,
                ctx.guild.id
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

        async with self.bot.pool.acquire() as conn:
            await conn.execute(
                'UPDATE guilds SET soundmaster = $1 WHERE id = $2',
                role.id,
                ctx.guild.id
            )
        await yes(ctx)

    @settings.command()
    @commands.check(is_botmaster)
    async def soundplayer(self, ctx: commands.Context, role: discord.Role):
        """
        Set the role that allows playing of sounds. By default anyone can play sounds.

        :param role: The role to make player of sounds.
        """

        async with self.bot.pool.acquire() as conn:
            await conn.execute(
                'UPDATE guilds SET soundplayer = $1 WHERE id = $2',
                role.id,
                ctx.guild.id
            )
        await yes(ctx)


def setup(bot):
    bot.add_cog(Settings(bot))
