import asyncio
import logging
import platform

from databases import Database
from discord import Message, Guild
from discord.ext import commands
from sqlalchemy import select

from .cogs.utils.reactions import no
from .config import Config
from .database import guilds

__all__ = ['SoundBert']

log = logging.getLogger(__name__)


async def get_prefix(bot: 'SoundBert', msg: Message):
    default_prefix = bot.config.default_prefix
    prefix = await bot.db.fetch_val(select([guilds.c.prefix]).where(guilds.c.id == msg.guild.id))
    return commands.when_mentioned_or(prefix if prefix else default_prefix)(bot, msg)


class SoundBert(commands.Bot):
    def __init__(self, config: Config):
        self._ensure_event_loop()
        super().__init__(command_prefix=get_prefix)

        self.config = config
        self.db = Database(config.database_url)
        self.loop.run_until_complete(self.db.connect())

        base_extensions = [
            'soundbert.cogs.soundboard',
            'soundbert.cogs.info',
            'soundbert.cogs.settings',
            'soundbert.cogs.admin'
        ]

        log.info('Loading base extensions.')
        for ext in base_extensions:
            self.load_extension(ext)
            log.debug(f'Loaded {ext}')

    @staticmethod
    def _ensure_event_loop():
        if platform.system() == 'Windows':
            loop = asyncio.ProactorEventLoop()
            asyncio.set_event_loop(loop)
        else:
            try:
                import uvloop

                asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            except ImportError:
                pass

    async def on_command_error(self, ctx: commands.Context, exception: commands.CommandError):
        log_msg = (
            f'In guild {ctx.guild.name}, channel {ctx.channel.name}, '
            f'{ctx.author.name} executed {ctx.message.content}, but encountered exception: {exception}'
        )
        if not isinstance(exception, commands.UserInputError):
            log.exception(log_msg, exc_info=exception)
        else:
            log.debug(log_msg)

        await no(ctx)
        if len(exception.args) > 0:
            msg = await ctx.send(exception.args[0])
            try:
                delay = int(exception.args[1])
            except (IndexError, ValueError):
                delay = 60
            await msg.delete(delay=delay)

    async def on_command(self, ctx: commands.Context):
        log.info(
                f'In guild {ctx.guild.name}, channel {ctx.channel.name}, '
                f'{ctx.author.name} executed {ctx.message.content}'
        )

    async def on_guild_join(self, guild: Guild):
        log.info(f'Joined guild {guild.name} ({guild.id}).')
        await self.db.execute(guilds.insert().values(id=guild.id))
