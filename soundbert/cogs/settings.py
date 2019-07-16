import discord
from discord.ext import commands

from .utils.reactions import yes
from ..soundbert import SoundBert


class Settings(commands.Cog):
    def __init__(self, bot: SoundBert):
        self.bot = bot

    @commands.group(invoke_without_command=True)
    async def settings(self, ctx: commands.Context):
        """
        Set bot server settings.
        """

        async with self.bot.pool.acquire() as conn:
            settings = await conn.fetchrow('SELECT prefix FROM guilds WHERE id = $1', ctx.guild.id)

        embed = discord.Embed()
        embed.title = 'Settings'

        for key, value in dict(settings).items():
            embed.add_field(name=key, value=value or 'Unset')

        await ctx.send(embed=embed)

    @settings.command()
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


def setup(bot):
    bot.add_cog(Settings(bot))
