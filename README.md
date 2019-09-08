# SoundBert

A soundboard for [discord](https://discordapp.com/).

## System Requirements

* Python3.6+
* `libopus0`
* `ffmpeg`
* PostgreSQL


## Setup and Running

Install SoundBert with `pip`:

1. Install the system requirements.
2. Install SoundBert and its dependencies with:
    ```commandline
    pip install git+https://github.com/dsluo/SoundBert.git@master
    ```
3. Set up PostgreSQL database with a user and corresponding database.
4. Create a file called `settings.toml`, structured as below:
    ```toml
    [bot]
    token = "<discord token here>"
    default_prefix = "!"
    verbose_errors = false
    db_uri = "<postgres database uri>"
    extra_cogs = []

    [logging]
    log_path = "./soundbert.logs"
    level = "DEBUG"

    [soundboard]
    path = "./sounds"
    ```
    where `db_uri` refers to the user and database created in step 3.
5. Run `soundbert migrate` to create the initial tables.
6. Run the bot with `soundbert run`.

## Commands

`!help`

```
Clipboard:
  clipboard A clipboard of text.
Info:
  about     Provides some basic info about the bot.
  invite    Get the invite link for this bot.
  source    Links the GitHub repository for the source of this bot.
  uptime    Displays time since the last restart.
Settings:
  settings  Set bot server settings.
SoundBoard:
  add       Add a new sound to the soundboard.
  delete    Delete a sound.
  info      Get info about a sound.
  last      Play the last sound played.
  list      List all the sounds on the soundboard.
  play      Play a sound.
  rand      Play a random sound.
  rename    Rename a sound.
  search    Search for a sound.
  stop      Stop playback of the current sound.
​No Category:
  help      Shows this message

Type !help command for more info on a command.
You can also type !help category for more info on a category.
```