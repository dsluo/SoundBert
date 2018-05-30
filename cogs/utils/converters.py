import datetime
import re

from discord.ext import commands


class DurationConverter(commands.Converter):
    regex = {
        'weeks':        re.compile(r'(\d+)\s*?(?:week|wk)s?'),
        'days':         re.compile(r'(\d+)\s*?(?:day|d)s?'),
        'minutes':      re.compile(r'(\d+)\s*?(?:minutes?|mins?|m)'),
        'seconds':      re.compile(r'(\d+)\s*?(?:seconds?|secs?|s)'),
        'milliseconds': re.compile(r'(\d+)\s*?(?:milliseconds?|millis?|ms)'),
        'microseconds': re.compile(r'(\d+)\s*?(?:microseconds?|micros?|us)')
    }

    @classmethod
    async def convert(cls, ctx, argument) -> datetime.timedelta:
        times = {
            i: j.search(argument)
            for i, j in cls.regex.items()
        }

        times = {i: int(j[1]) for i, j in times.items() if j}

        return datetime.timedelta(**times)
