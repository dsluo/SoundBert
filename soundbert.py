import logging

import asyncpg
from discord.ext import commands

from cogs.utils.reactions import no

log = logging.getLogger(__name__)


class SoundBert(commands.Bot):
    def __init__(self, config):
        prefix = config.get('default_prefix', '!')
        super().__init__(prefix)

        self.config = config
        self.pool = self.loop.run_until_complete(asyncpg.create_pool(config['db_uri']))

        extensions = [
            'cogs.soundboard',
            'cogs.info'
        ]

        for ext in extensions:
            self.load_extension(ext)

    def run(self):
        super(SoundBert, self).run(self.config['token'])

    async def on_command_error(self, ctx: commands.Context, exception: commands.CommandError):
        if len(exception.args) > 0:
            await ctx.send(exception.args[0])
        else:
            await no(ctx)
