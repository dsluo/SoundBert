from discord.ext import commands

from .utils.reactions import yes
from ..soundbert import SoundBert


class Settings(commands.Cog):
    def __init__(self, bot: SoundBert):
        self.bot = bot

    @commands.group()
    async def settings(self, ctx: commands.Context):
        pass

    @settings.command(name='prefix')
    async def set_prefix(self, ctx: commands.Context, prefix):
        """
        Set the prefix for this server (the symbol that specifies that a message is a command,
        e.g. !play -> -play).

        :param prefix: The new prefix
        """
        async with self.bot.pool.acquire() as conn:
            await conn.execute(
                'UPDATE guilds SET prefix = $1 WHERE id = $2',
                prefix,
                ctx.guild.id
            )
        await yes(ctx)

def setup(bot):
    bot.add_cog(Settings(bot))
