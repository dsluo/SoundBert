import enum

from soundbert.cogs.utils.pluralize import pluralize


class TimeUnits(enum.IntEnum):
    DAYS = 1
    HOURS = 2
    MINUTES = 3
    SECONDS = 4
    MILLISECONDS = 5
    MICROSECONDS = 6


def humanduration(seconds: float, granularity=TimeUnits.SECONDS):
    days, rem = divmod(seconds, 24 * 60 * 60)
    hours, rem = divmod(rem, 60 * 60)
    minutes, rem = divmod(rem, 60)
    seconds_, rem = divmod(rem, 1)
    milliseconds, rem = divmod(rem, 0.001)
    microseconds = rem / 0.000001

    timestring = []
    if days and granularity >= TimeUnits.DAYS:
        timestring.append(f'**{days:g}** {pluralize(days, "day")}')
    if hours and granularity >= TimeUnits.HOURS:
        timestring.append(f'**{hours:g}** {pluralize(hours, "hour")}')
    if minutes and granularity >= TimeUnits.MINUTES:
        timestring.append(f'**{minutes:g}** {pluralize(minutes, "minute")}')
    if seconds_ and granularity >= TimeUnits.SECONDS:
        timestring.append(f'**{seconds_:g}** {pluralize(seconds_, "second")}')
    if milliseconds and granularity >= TimeUnits.MILLISECONDS:
        timestring.append(f'**{milliseconds:g}** {pluralize(milliseconds, "millisecond")}')
    if microseconds and granularity >= TimeUnits.MICROSECONDS:
        timestring.append(f'**{microseconds}** {pluralize(microseconds, "microsecond")}')

    return ' '.join(timestring)
