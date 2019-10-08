from datetime import datetime

from discord.ext import commands

from .utils.humantime import humanduration
from ..soundbert import SoundBert


class Info(commands.Cog):
    def __init__(self, bot: 'SoundBert'):
        self.bot = bot

        if not hasattr(bot, 'startup'):
            self.bot.startup = datetime.now()

    @commands.command()
    async def invite(self, ctx: commands.Context):
        """
        Get the invite link for this bot.
        """
        await ctx.send(
            f'https://discordapp.com/api/oauth2/authorize?client_id={self.bot.user.id}&permissions=3172416&scope=bot'
        )

    @commands.command()
    async def source(self, ctx: commands.Context):
        """
        Links the GitHub repository for the source of this bot.
        """
        await ctx.send('https://github.com/dsluo/SoundBert/')

    @commands.command()
    async def about(self, ctx: commands.Context):
        """
        Provides some basic info about the bot.
        """
        await ctx.send('SoundBert by dsluo\n'
                       'Written in Python using discord.py\n'
                       'https://github.com/dsluo/SoundBert/')

    @commands.command()
    async def uptime(self, ctx: commands.Context):
        """
        Displays time since the last restart.
        """
        time = datetime.now() - self.bot.startup

        uptime = humanduration(time.total_seconds())
        await ctx.send(f'Uptime: {uptime}.')


def setup(bot):
    bot.add_cog(Info(bot))
