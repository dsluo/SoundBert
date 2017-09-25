# SoundBot

A soundboard for [discord](https://discordapp.com/).

## Requirements


* [`discord.py[voice]`](https://github.com/Rapptz/discord.py)
* `PyNaCl` (should be taken care of with the `[voice]` install option.
* `libopus0`
* `ffmpeg`
* Python3.6+

## Setup and Running

1. Create a virtualenv and install the requirements in `requirements.txt`.
2. Create a file called token.txt and paste in your bot token.
3. Change into the SoundBot root directory.
4. Run the bot with `nohup python3 -m soundbot &`

## Commands

| Command                  | Function                                 |
| -------                  | --------                                 |
| `!<name> [vXX] [sYY]`    | Play a sound at XX% volume and YY% speed |
| `+<name> <link>`         | Add a new sound                          |
| `-<name>`                | Remove a sound                           |
| `~<name> <new_name>`     | Rename a sound                           |
| `$list`                  | Print a list of all sounds               |
| `$stop`                  | Force stop sound playback                |
| `$stat <name>`           | Get playback stats for a sound           |
| `$help`                  | Print help message                       |
