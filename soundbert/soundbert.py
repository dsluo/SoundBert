import logging

import asyncpg
from discord import Message
from discord.ext import commands
from discord.ext.commands import ExtensionNotFound

from .cogs.utils.reactions import no

__all__ = ['SoundBert']

log = logging.getLogger(__name__)


async def get_prefix(bot: 'SoundBert', msg: Message):
    default_prefix = bot.config['bot']['default_prefix']
    async with bot.pool.acquire() as conn:
        prefix = await conn.fetchval('SELECT prefix FROM guilds WHERE id = $1', msg.guild.id)
    return commands.when_mentioned_or(prefix if prefix else default_prefix)(bot, msg)


class SoundBert(commands.Bot):
    def __init__(self, config):
        super().__init__(command_prefix=get_prefix)

        self.config = config
        self.pool = self.loop.run_until_complete(asyncpg.create_pool(config['bot']['db_uri']))

        base_extensions = [
            'soundbert.cogs.soundboard',
            'soundbert.cogs.info',
            'soundbert.cogs.settings',
            'soundbert.cogs.admin'
        ]

        log.debug('Loading base extensions.')
        for ext in base_extensions:
            self.load_extension(ext)

        log.debug('Loading extra extensions.')
        for ext in config['bot']['extra_cogs']:
            try:
                self.load_extension(ext)
            except ExtensionNotFound:
                log.exception('Failed to load extension.')

    async def on_command_error(self, ctx: commands.Context, exception: commands.CommandError):
        log.debug(exception)
        if self.config['bot']['verbose_errors']:
            if len(exception.args) > 0:
                await ctx.send(exception.args[0])
        else:
            await no(ctx)

    async def on_command(self, ctx: commands.Context):
        log.debug(ctx.message)
