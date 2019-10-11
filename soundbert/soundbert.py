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
        log.exception(
            f'In guild {ctx.guild.name}, channel {ctx.channel.name}, '
            f'{ctx.author.name} executed {ctx.message.content}, but encountered exception:\n'
            f'{exception}',
            exc_info=exception
        )
        await no(ctx)
        if len(exception.args) > 0:
            msg = await ctx.send(exception.args[0])
            try:
                delay = int(exception.args[1])
            except (IndexError, ValueError):
                delay = 60
            await msg.delete(delay=delay)

    async def on_command(self, ctx: commands.Context):
        log.debug(
            f'In guild {ctx.guild.name}, channel {ctx.channel.name}, '
            f'{ctx.author.name} executed {ctx.message.content}'
        )
