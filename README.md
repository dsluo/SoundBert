# SoundBert
[![FOSSA Status](https://app.fossa.io/api/projects/git%2Bgithub.com%2Fdsluo%2FSoundBert.svg?type=shield)](https://app.fossa.io/projects/git%2Bgithub.com%2Fdsluo%2FSoundBert?ref=badge_shield)


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

| Command                         | Function                                     |
| ------------------------------- | -------------------------------------------- |
| `!play <name> [vXX] [sYY]`      | Play a sound at `XX%` volume and `YY%` speed |
| `!add <name> <link>`            | Add a new sound                              |
| `!delete <name>`                | Remove a sound                               |
| `!rename <name> <new_name>`     | Rename a sound                               |
| `!rand`                         | Play a random sound                          |
| `!stop`                         | Force stop sound playback                    |
| `!list`                         | Print a list of all sounds                   |
| `!stat <name>`                  | Get playback stats for a sound               |
| `!help`                         | Print help message                           |



## License
[![FOSSA Status](https://app.fossa.io/api/projects/git%2Bgithub.com%2Fdsluo%2FSoundBert.svg?type=large)](https://app.fossa.io/projects/git%2Bgithub.com%2Fdsluo%2FSoundBert?ref=badge_large)