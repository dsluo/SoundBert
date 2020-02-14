from discord.ext import commands


class NotSoundmaster(commands.MissingRole):
    def __init__(self, soundmaster_role):
        super(NotSoundmaster, self).__init__(f'You need the `@{soundmaster_role}` role to manage sounds.')


class NotSoundplayer(commands.MissingRole):
    def __init__(self, soundplayer_role):
        super(NotSoundplayer, self).__init__(f'You need the `@{soundplayer_role}` role to play sounds.')


class NoChannel(commands.UserInputError):
    def __init__(self):
        super(NoChannel, self).__init__('You are not in a voice channel.')


class SoundDoesNotExist(commands.BadArgument):
    def __init__(self, name, suggestions=None):
        if suggestions:
            super(SoundDoesNotExist, self).__init__(f'Sound `{name}` does not exist. Did you mean:\n{suggestions}')
        else:
            super(SoundDoesNotExist, self).__init__(f'Sound `{name}` does not exist.')


class SoundExists(commands.BadArgument):
    def __init__(self, name):
        super(SoundExists, self).__init__(f'Sound `{name}` already exists.')


class AliasTargetIsAlias(commands.BadArgument):
    def __init__(self):
        super(AliasTargetIsAlias, self).__init__('Cannot create alias of an alias.')


class NegativeVolume(commands.BadArgument):
    def __init__(self):
        super(NegativeVolume, self).__init__('Volume cannot be less than 0%.')


class NegativeSpeed(commands.BadArgument):
    def __init__(self):
        super(NegativeSpeed, self).__init__('Speed cannot be less than 0%.')


class BadPlaybackArgs(commands.ArgumentParsingError):
    def __init__(self, args):
        super(BadPlaybackArgs, self).__init__(f'Cound not parse `{args}`.')

class BadPlaybackRange(commands.UserInputError):
    def __init__(self, min, max, arg):
        super(BadPlaybackRange, self).__init__(f'{arg.capitalize()} must be between {min} and {max}.')


class NoDownload(commands.BadArgument):
    def __init__(self):
        super(NoDownload, self).__init__('Download link or file attachment required.')


class DownloadError(commands.CommandError):
    def __init__(self):
        super(DownloadError, self).__init__('Error while downloading.')


class NoSounds(commands.CommandError):
    def __init__(self):
        super(NoSounds, self).__init__('No sounds yet.')


class InvalidSoundName(commands.CommandError):
    def __init__(self, message='Invalid sound name.', *args: object):
        super(InvalidSoundName, self).__init__(message=message, *args)
