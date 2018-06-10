# SoundBert

A soundboard for [discord](https://discordapp.com/).

## System Requirements

* Python3.6+
* `libopus0`
* `ffmpeg`
* PostgreSQL

## Setup and Running

1. Install the system requirements.
2. Create a virtualenv and install the requirements in `requirements.txt`.
3. Set up PostgreSQL database with a user and corresponding database.
4. Create a file called `config.json`, structured as below:
    ```json
    {
      "token": "<discord token>",
      "db_uri": "<postgres uri>"
    }
    ```
    where `db_uri` refers to the user and database created in step 3.
5. Run `db_init.sql` script on the database to create initial tables.
6. Activate the virtualenv, and run the bot with `launcher config.json`

## Commands

`!help`

```
Info:
  info   Provides some basic info about the bot.
  invite Get the invite link for this bot.
  source Links the GitHub repository for the source of this bot.
  uptime Displays time since the last restart.
SoundBoard:
  add    Add a new sound to the soundboard.
  delete Delete a sound.
  list   List all the sounds on the soundboard.
  mute   Mute the specified sound for a certain amount of time.
  play   Play a sound.
  rand   Play a random sound.
  rename Rename a sound.
  stat   Get stats of a sound.
  stop   Stop playback of the current sound.
  unmute Unmute the specified sound.
​No Category:
  help   Shows this message.

Type !help command for more info on a command.
You can also type !help category for more info on a category.
```