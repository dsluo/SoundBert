from datetime import datetime
from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from soundbert import SoundBert


class Info:
    def __init__(self, bot: 'SoundBert'):
        self.bot = bot

        self.startup = datetime.now()

    @commands.command()
    async def invite(self, ctx: commands.Context):
        client_id = await self.bot.user.id
        await ctx.send(
            f'https://discordapp.com/api/oauth2/authorize?client_id={client_id}&permissions=0&scope=bot'
        )

    @commands.command()
    async def source(self, ctx: commands.Context):
        await ctx.send('https://github.com/davidsluo/SoundBert/')

    @commands.command()
    async def info(self, ctx: commands.Context):
        await ctx.send('SoundBert by davidsluo\n'
                       'Written in Python using discord.py\n'
                       'https://github.com/davidsluo/SoundBert/')

    @commands.command()
    async def uptime(self, ctx:commands.Context):
        await ctx.send(datetime.now() - self.startup)


def setup(bot):
    bot.add_cog(Info(bot))
