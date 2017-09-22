# SoundBot

A soundboard for [discord](https://discordapp.com/).

## Requirements


* [`discord.py[voice]`](https://github.com/Rapptz/discord.py)
* `PyNaCl`

## Setup and Running

Create a file called token.txt and paste in your bot token.

_**TODO**_: how to actually run the bot

## Commands

| Command                  | Function                                 |
| -------                  | --------                                 |
| `!<name> [vXX] [sYY]`    | Play a sound at XX% volume and YY% speed |
| `+<name> <link>`         | Add a new sound                          |
| `-<name>`                | Remove a sound                           |
| `~<name> <new_name>`     | Rename a sound                           |
| `$list`                  | Print a list of all sounds               |
| `$stop`                  | Force stop sound playback                |
| `$help`                  | Print help message                       |
