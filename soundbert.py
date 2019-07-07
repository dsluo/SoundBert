import logging

import asyncpg
from discord import Message
from discord.ext import commands

from cogs.utils.reactions import no

log = logging.getLogger(__name__)

VERBOSE_ERRORS = False


async def get_prefix(bot: 'SoundBert', msg: Message):
    async with bot.pool.acquire() as conn:
        prefix = await conn.fetchval('SELECT prefix FROM guilds WHERE id = $1', msg.guild.id)
    return commands.when_mentioned_or(prefix if prefix else '!')(bot, msg)


class SoundBert(commands.Bot):
    def __init__(self, config):
        super().__init__(command_prefix=get_prefix)

        self.config = config
        self.pool = self.loop.run_until_complete(asyncpg.create_pool(config['db_uri']))

        extensions = [
            'cogs.soundboard',
            'cogs.info',
            'cogs.settings'
        ]

        for ext in extensions:
            self.load_extension(ext)

    def run(self):
        super(SoundBert, self).run(self.config['token'])

    async def on_command_error(self, ctx: commands.Context, exception: commands.CommandError):
        if VERBOSE_ERRORS:
            if len(exception.args) > 0:
                await ctx.send(exception.args[0])
            else:
                await no(ctx)

        log.error('Encountered exception while executing command:', exc_info=exception)
