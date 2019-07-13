import asyncpg
from discord import Message
from discord.ext import commands

from .cogs.utils.reactions import no

__all__ = ['SoundBert']


async def get_prefix(bot: 'SoundBert', msg: Message):
    default_prefix = bot.config['bot'].get('default_prefix', '!')
    async with bot.pool.acquire() as conn:
        prefix = await conn.fetchval('SELECT prefix FROM guilds WHERE id = $1', msg.guild.id)
    return commands.when_mentioned_or(prefix if prefix else default_prefix)(bot, msg)


class SoundBert(commands.Bot):
    def __init__(self, config):
        super().__init__(command_prefix=get_prefix)

        self.config = config
        self.pool = self.loop.run_until_complete(asyncpg.create_pool(config['bot']['db_uri']))

        extensions = [
            'soundbert.cogs.soundboard',
            'soundbert.cogs.info',
            'soundbert.cogs.settings',
            *config['bot'].get('extra_cogs', [])
        ]

        for ext in extensions:
            self.load_extension(ext)

    async def on_command_error(self, ctx: commands.Context, exception: commands.CommandError):
        if self.config['bot']['verbose_errors']:
            if len(exception.args) > 0:
                await ctx.send(exception.args[0])
            else:
                await no(ctx)
