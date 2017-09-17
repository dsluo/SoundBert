import hashlib
import json
import os
from json import JSONDecodeError

import aiohttp
import asyncio
import discord
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

sound_dir = os.getcwd() + '/sounds'


class SoundBot(discord.Client):
    def __init__(self, **options):
        super().__init__(**options)

        self.sounds = {}

        if not os.path.isdir(sound_dir):
            os.mkdir(sound_dir)

        try:
            log.info('Loading sounds...')

            with open('sounds.json', 'r') as f:
                sounds = json.load(f)

            for name, hash in sounds.items():
                self.sounds[name] = hash

                log.info(f'Loaded {name}: {hash}')

        except FileNotFoundError:
            log.info('No sounds file. Creating sound database file.')

            with open('sounds.json', 'w') as f:
                f.write('{}')

        except JSONDecodeError:
            log.error('Malformed sound database file.')

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
        try:
            sound = self.sounds[name]
        except KeyError:
            await self.send_message(msg.channel, f'Sound **{name}** does not exist.')
            return

        channel = msg.author.voice_channel

        if channel is None:
            await self.send_message(msg.channel, 'You are not in a voice channel!')
            return

        if not self.is_voice_connected(msg.server):
            client = await self.join_voice_channel(channel)
        else:
            client = self.voice_client_in(msg.server)

        notifier = asyncio.Event()

        player = client.create_ffmpeg_player(f'{sound_dir}/{sound}', after=lambda: notifier.set())
        player.start()

        await notifier.wait()
        await client.disconnect()

    async def add_sound(self, msg: discord.Message, name: str, link: str = None):
        # Disallow duplicate names
        if name in self.sounds.keys():
            await self.send_message(msg.channel, f'Sound named {name} already exists.')
            return

        # Resolve download url.
        if link is None:
            try:
                link = msg.attachments[0]['url']
                log.info(f'Adding sound "{name}" from attachment "{link}".')
            except (IndexError, KeyError):
                await self.send_message(msg.channel, 'Link or attachment required.')
        else:
            log.info(f'Adding sound "{name}" from "{link}".')

        # Download file
        log.info(f'Downloading from {link}')
        async with aiohttp.ClientSession() as session:
            async with session.get(link) as resp:
                log.info(f'Received response {resp.status}: {resp.reason}.')
                if resp.status == 200:

                    # Write response to temporary file and moves it to the /sounds directory when done.
                    # Filename = blake2 hash of file
                    hash = hashlib.blake2s()
                    with open(f'{os.getcwd()}/tempsound', 'wb') as f:
                        while True:
                            chunk = await resp.content.read(1024)
                            if not chunk:
                                break
                            hash.update(chunk)
                            f.write(chunk)

                    filename = hash.hexdigest().upper()

                    try:
                        os.rename(f'{os.getcwd()}/tempsound', f'{sound_dir}/{filename}')

                        self.sounds[name] = filename
                        log.info(f'Saved {name} as {filename}.')
                        await self.send_message(msg.channel, f'Saved **{name}**.')
                        self._update_json()
                    except FileExistsError:
                        await self.send_message(msg.channel, f'Sound already exists.')

                else:
                    await self.send_message(msg.channel, f'Error while downloading: {resp.reason}.')
                await resp.release()

    async def remove_sound(self, msg: discord.Message, name: str):
        if name not in self.sounds.keys():
            await self.send_message(msg.channel, f'Sound **{name}** does not exist.')
            return

        sound = self.sounds.pop(name)
        os.remove(f'{sound_dir}/{sound}')
        await self.send_message(msg.channel, f'Removed **{name}**.')
        self._update_json()

    async def rename_sound(self, msg: discord.Message, name: str, new_name: str):
        try:
            sound = self.sounds.pop(name)
        except KeyError:
            await self.send_message(msg.channel, f'Sound **{name}** does not exist.')
            return

        self.sounds[new_name] = sound
        await self.send_message(msg.channel, f'**{name}** renamed to **{new_name}**.')
        self._update_json()

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
        if len(self.sounds) == 0:
            message = 'No sounds yet. Add one with `+<name> <link>`!'
        else:
            sounds = ', '.join(self.sounds)
            message = f'Sounds:\n{sounds}'
        await self.send_message(msg.channel, message)

    def _update_json(self):
        with open('sounds.json', 'w') as f:
            json.dump(self.sounds, f)


def main():
    bot = SoundBot()

    log.info('Loading token.')
    with open('token.txt', 'r') as f:
        token = f.read()

    log.info('Starting bot.')
    bot.run(token)
