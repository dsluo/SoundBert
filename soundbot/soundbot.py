import json
from json import JSONDecodeError

import discord
import logging

log = logging.getLogger(__name__)


class Sound:
    def __init__(self, name: str, hash: str):
        self.name = name
        self.hash = hash


class SoundBot(discord.Client):
    sounds = []

    def __init__(self, **options):

        super().__init__(**options)

        try:
            log.info('Loading sounds...')

            with open('sounds.json', 'r') as f:
                sounds = json.loads(f)

            for sound in sounds:
                name = sound['name']
                hash = sound['hash']

                self.sounds.append(Sound(name, hash))

                log.debug(f'Loaded {name}: {hash}')
        except FileNotFoundError:
            log.info('No sounds file. Creating sound file.')

            with open('sounds.json', 'w') as f:
                f.write('')

        except JSONDecodeError as e:
            log.error('Malformed sound file.')

    async def on_message(self, msg: discord.Message):
        if len(msg.content) <= 1:
            return

        prefix = msg.content[0]
        text = msg.content[1:].split()

        if prefix == '!':
            await self.play_sound(msg, *text)
        elif prefix == '+':
            await self.add_sound(msg, *text)
        elif prefix == '-':
            await self.remove_sound(msg, *text)
        elif prefix == '~':
            await self.rename_sound(msg, *text)
        elif prefix == '$':
            arg = text[0]
            if arg == 'help':
                await self.help(msg)
            elif arg == 'list':
                await self.list(msg)

    async def play_sound(self, msg: discord.Message, name: str):
        channel: discord.Channel = msg.author.voice.voice_channel

        if channel == None:
            # await self.send_message(msg.channel, 'You are not in a voice channel!')
            return

    async def add_sound(self, msg: discord.Message, name: str, link: str):
        pass

    async def remove_sound(self, msg: discord.Message, name: str):
        pass

    async def rename_sound(self, msg: discord.Message, name: str, new_name: str):
        pass

    async def help(self, msg: discord.Message):
        help_msg = (
            '```\n'
            '+------------------------+----------------------------+\n'
            '| Command                | Function                   |\n'
            '+------------------------+----------------------------+\n'
            '| !<name>                | Play a sound               |\n'
            '| +<name> <link>         | Add a new sound            |\n'
            '| -<name>                | Remove a sound             |\n'
            '| ~<name> <new_name>     | Rename a sound             |\n'
            '| $list                  | Print a list of all sounds |\n'
            '| $help                  | Print this message         |\n'
            '+------------------------+----------------------------+\n'
            '```'
        )

        await self.send_message(msg.channel, help_msg)

    async def list(self, msg: discord.Message):
        pass


def main():
    bot = SoundBot()

    log.info('Loading token.')
    with open('token.txt', 'r') as f:
        token = f.read()

    log.info('Starting bot.')
    bot.run(token)
