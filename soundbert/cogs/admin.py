from discord.ext import commands

from ..soundbert import SoundBert


class Admin(commands.Cog, command_attrs=dict(hidden=True)):
    def __init__(self, bot: 'SoundBert'):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context):
        return await self.bot.is_owner(ctx.author)


def setup(bot):
    bot.add_cog(Admin(bot))
