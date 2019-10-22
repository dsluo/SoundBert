# Changelog

* [0.3.0](#0.3.0)
* [0.3.1](#0.3.1)
* [0.3.2](#0.3.2)
* [0.4.0](#0.4.0)

## 0.3.0

* Added a basic permissions system.

    Server admins need a `soundmaster` and `soundplayer` role and set them 
    to be as such using `!settings soundmaster <role>` and 
    `!settings soundplayer <role>` respectively. Soundmasters can add/remove
    sounds, and soundplayers can list sounds, play sounds, etc. By default,
    anyone can do anything.

## 0.3.1

* Temporary fix for Discord voice connect issues using v1.3.0a (dev version) of `discord.py`.

## 0.3.2

* Permanent fix for Discord voice connect issues using v1.2.4 (production version) of `discord.py`.

## 0.4.0

* Added sound aliases. User `!alias <name> <alias>` to give a sound an alias. 
* Removed unused `!last` command.
* Improved logging.
