import asyncio
import logging
import platform

from async_lru import alru_cache
from asyncpg import UniqueViolationError
from databases import Database
from discord import Message
from discord.ext import commands
from sqlalchemy import select

from .cogs.utils.reactions import err, warn
from .config import Config
from .database import guilds

__all__ = ['SoundBert']

log = logging.getLogger(__name__)


class SoundBert(commands.Bot):
    def __init__(self, config: Config):
        self._ensure_event_loop()
        super().__init__(command_prefix=SoundBert._get_guild_prefix)

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

        log.info('Loading extra extensions.')
        for ext in self.config.extra_extensions.split(','):
            ext = ext.strip()
            try:
                self.load_extension(ext)
            except commands.ExtensionNotFound:
                log.exception(f'Failed to load {ext}.')
            else:
                log.debug(f'Loaded {ext}.')

    def run(self):
        super(SoundBert, self).run(self.config.token)

    @staticmethod
    def _ensure_event_loop():
        """
        Allows for subprocessing using asyncio on Windows, and tries to use uvloop on Unix-like systems.
        """
        if platform.system() == 'Windows':
            loop = asyncio.ProactorEventLoop()
            asyncio.set_event_loop(loop)
        else:
            try:
                import uvloop

                asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            except ImportError:
                pass

    async def _get_guild_prefix(self, msg: Message):
        """
        Implementation for command_prefix.

        :param msg: The message that might have a command.
        :return: The prefix
        """
        await self._ensure_guild(msg.guild.id)
        prefix = await self.db.fetch_val(select([guilds.c.prefix]).where(guilds.c.id == msg.guild.id))
        return commands.when_mentioned_or(prefix)(self, msg)

    @alru_cache(maxsize=2048)
    async def _ensure_guild(self, guild_id: int):
        """
        Ensures that the guild is in the database. Uses an LRU cache to try to not ping the database too much.

        :param guild_id: The guild id
        """
        log.debug(f'Ensuring guild {guild_id} is in database.')
        query = guilds.insert().values(id=guild_id, prefix=self.config.default_prefix)
        try:
            await self.db.execute(query)
        except UniqueViolationError:
            pass

    async def on_command_error(self, ctx: commands.Context, exception: commands.CommandError):
        """
        Error handling.

        :param ctx: Command context
        :param exception: What went wrong
        """
        log_msg = (
            f'In guild {ctx.guild.name}, channel {ctx.channel.name}, '
            f'{ctx.author.name} executed {ctx.message.content}, but encountered exception: {exception}'
        )
        if isinstance(exception, (commands.UserInputError, commands.CheckFailure, commands.CommandOnCooldown)):
            log.debug(log_msg)
            await warn(ctx)
        else:
            log.exception(log_msg, exc_info=exception)
            await err(ctx)

        if len(exception.args) > 0:
            try:
                delay = int(exception.args[1])
            except (IndexError, ValueError):
                delay = 60
            await ctx.send(exception.args[0], delete_after=delay)

    async def on_command(self, ctx: commands.Context):
        """
        Log command execution.

        :param ctx: Command context
        """
        log.info(
                f'In guild {ctx.guild.name}, channel {ctx.channel.name}, '
                f'{ctx.author.name} executed {ctx.message.content}'
        )
