import logging

import pathvalidate
from discord.ext import commands
from pathvalidate import ValidationError, InvalidLengthError, ReservedNameError, InvalidCharError
from pathvalidate._filename import FileNameValidator
from sqlalchemy import and_, exists, select

from . import exceptions
from ...database import sounds, sound_names

log = logging.getLogger(__name__)


class SoundConverter(commands.Converter):
    def __init__(self, columns):
        self.columns = columns

    async def convert(self, ctx: commands.Context, name):
        if len(self.columns) == 1:
            fetch = ctx.bot.db.fetch_val
        else:
            fetch = ctx.bot.db.fetch_one

        return await fetch(
                select(self.columns)
                    .select_from(sounds.join(sound_names))
                    .where(and_(
                        sound_names.c.guild_id == ctx.guild.id,
                        sound_names.c.name == name
                ))
        )


class ExistingSound(SoundConverter):
    def __init__(self, columns, *, suggestions=False):
        super().__init__(columns)
        self.suggestions = suggestions

    async def convert(self, ctx: commands.Context, name):
        sound = await super(ExistingSound, self).convert(ctx, name)
        if sound is None:
            if self.suggestions:
                from . import SoundBoard
                records = await SoundBoard._search(ctx.bot.db, ctx.guild.id, name)
                if len(records) > 0:
                    suggestions = '\n'.join(record[sound_names.c.name] for record in records)
                    raise exceptions.SoundDoesNotExist(name, suggestions)
            raise exceptions.SoundDoesNotExist(name)
        return sound


class NewSound(SoundConverter):
    """
    Converter that ensures that a new sound name is valid.
    """
    def __init__(self):
        super().__init__([exists([1])])
        self.validator = FileNameValidator()

    async def convert(self, ctx: commands.Context, name):

        try:
            self.validator.validate(name)
        except ValidationError as e:
            log.exception(f'{ctx.author} (id={ctx.author.id}) tried to add sound {name}, which is invalid.')
            if isinstance(e, InvalidLengthError):
                raise exceptions.InvalidSoundName(
                        f'Sound names must be between 1 and {self.validator.max_len} characters in length.')
            elif isinstance(e, InvalidCharError):
                sanitized = pathvalidate.sanitize_filename(name)
                invalid = set(name) - set(sanitized)

                raise exceptions.InvalidSoundName(f'Sound name contains invalid characters: `{invalid}`')
            elif isinstance(e, ReservedNameError):
                raise exceptions.InvalidSoundName(f'Sounds cannot be named `{e.reserved_name}`.')
            else:
                raise exceptions.InvalidSoundName()

        exists = await super(NewSound, self).convert(ctx, name)
        if exists:
            raise exceptions.SoundExists(name)
        return pathvalidate.sanitize_filename(name)
