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
        """
        Get the invite link for this bot.
        """
        await ctx.send(
            f'https://discordapp.com/api/oauth2/authorize?client_id={self.bot.user.id}&permissions=0&scope=bot'
        )

    @commands.command()
    async def source(self, ctx: commands.Context):
        """
        Links the GitHub repository for the source of this bot.
        """
        await ctx.send('https://github.com/dsluo/SoundBert/')

    @commands.command()
    async def info(self, ctx: commands.Context):
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
        time = datetime.now() - self.startup

        days = time.days
        minutes, seconds = divmod(time.seconds, 60)
        hours, minutes = divmod(minutes, 60)
        await ctx.send('Uptime: '
                       f'**{days}** day{"" if days == 1 else "s"} '
                       f'**{hours}** hour{"" if hours == 1 else "s"} '
                       f'**{minutes}** minute{"" if minutes == 1 else "s"} '
                       f'**{seconds}** second{"" if seconds == 1 else "s"}.')


def setup(bot):
    bot.add_cog(Info(bot))
