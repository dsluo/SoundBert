from pathlib import Path

import toml
from discord.ext import commands

from .utils.reactions import yes
from ..soundbert import SoundBert


class Admin(commands.Cog):
    def __init__(self, bot: 'SoundBert'):
        self.bot = bot

    cog_check = commands.is_owner

    @commands.command()
    async def reload_config(self, ctx: commands.Context, path=None):
        if path is not None:
            path = Path(path)
        else:
            path = Path('settings.toml')

        try:
            with path.open('r') as f:
                config = toml.load(f)

            del config['bot']['token']  # probably dont want this in memory

            self.bot.config = config

            await yes(ctx)
        except toml.TomlDecodeError:
            await ctx.send('Error decoding settings file.')
        except OSError:
            await ctx.send('Could not open settings file.')

def setup(bot):
    bot.add_cog(Admin(bot))