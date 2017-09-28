# SoundBert

A soundboard for [discord](https://discordapp.com/).

## System Requirements

* Python3.6+
* `libopus0`
* `ffmpeg`
* MongoDB (preferably locally)

## Setup and Running

1. Install the system requirements.
2. Create a virtualenv and install the requirements in `requirements.txt`.
3. Create a file called `config.json`, structured as below:
    ```json
    {
      "token": "<discord token>",
      "db_uri": "<mongodb uri>",
      "db_name": "<name of database to use>"
    }
    ```
4. Activate the virtualenv, and run the bot with `nohup python3 -m soundbert &`

## Commands

| Command                  | Function                                     |
| ------------------------ | -------------------------------------------- |
| `!<name> [vXX] [sYY]`    | Play a sound at `XX%` volume and `YY%` speed |
| `+<name> <link>`         | Add a new sound                              |
| `-<name>`                | Remove a sound                               |
| `~<name> <new_name>`     | Rename a sound                               |
| `$list`                  | Print a list of all sounds                   |
| `$stop`                  | Force stop sound playback                    |
| `$stat <name>`           | Get playback stats for a sound               |
| `$help`                  | Print help message                           |
