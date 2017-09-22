import asyncio
import hashlib
import json
import logging
import os
from collections import OrderedDict
from json import JSONDecodeError

import aiohttp
import discord

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

sound_dir = os.getcwd() + '/sounds'


class SoundBot(discord.Client):
    def __init__(self, **options):
        super().__init__(**options)

        self.sounds = {}

        if not os.path.isdir(sound_dir):
            log.debug(f'Sound directory "{sound_dir}" not found. Creating...')
            os.mkdir(sound_dir)
        else:
            log.debug(f'Using existing sound directory "{sound_dir}". ')

        try:
            log.debug('Reading sounds database...')
            with open('sounds.json', 'r') as f:
                sounds = json.load(f)

            for name, hash in sounds.items():
                log.debug(f'Registering sound "{name}" with hash {hash}.')
                self.sounds[name] = hash

        except FileNotFoundError:

            log.debug('Sound database not found. Creating new empty database.')
            with open('sounds.json', 'w') as f:
                f.write('{}')

        except JSONDecodeError:
            log.error('Malformed sounds database file (sounds.json).')

    async def on_message(self, msg: discord.Message):
        if len(msg.content) <= 1:
            return

        prefix = msg.content[0]
        text = msg.content[1:].split()

        if prefix == '!':
            log.debug('Received sound command.')
            speed = None
            volume = None

            for word in text[1:]:
                if word.startswith('s'):
                    try:
                        speed = int(word[1:])
                        log.debug(f'Using speed {speed}%.')
                        break
                    except ValueError:
                        log.debug(f'Could not parse speed argument {word}.')

            for word in text[1:]:
                if word.startswith('v'):
                    try:
                        log.debug(f'Using speed {volume}%.')
                        volume = int(word[1:])
                        break
                    except ValueError:
                        log.debug(f'Could not parse volume argument {word}.')

            if speed is None:
                log.debug(f'Using default speed {speed}%.')
                speed = 100
            if volume is None:
                volume = 50
                log.debug(f'Using default volume {volume}%.')

            await self.play_sound(msg, text[0], speed, volume)
        elif prefix == '+':
            log.debug('Received add sound command.')
            await self.add_sound(msg, *text)
        elif prefix == '-':
            log.debug('Received remove sound command.')
            await self.remove_sound(msg, *text)
        elif prefix == '~':
            log.debug('Received rename sound command.')
            await self.rename_sound(msg, *text)
        elif prefix == '$':
            arg = text[0]
            if arg == 'help':
                log.debug('Received help command.')
                await self.help(msg)
            elif arg == 'list':
                log.debug('Received list sounds command.')
                await self.list(msg)
            elif arg == 'stop':
                log.debug('Received stop playback command.')
                await self.stop(msg)

    async def play_sound(self, msg: discord.Message, name: str, speed: int = 100, volume: int = 100):
        try:
            sound = self.sounds[name]
        except KeyError:
            await self.send_message(msg.channel, f'Sound **{name}** does not exist.')
            return

        if len(msg.mentions) == 1 and msg.mention_everyone is False:
            channel = msg.mentions[0].voice_channel
        else:
            channel = msg.author.voice_channel

        if channel is None:
            await self.send_message(msg.channel, f'Invalid target voice channel.')
            return

        speed = min(speed, 200)
        speed = max(speed, 50)

        log.info(f'Playing "{name}" in server "{msg.server}", channel "{channel}" at {speed}% speed, {volume}% volume.')
        if not self.is_voice_connected(msg.server):
            client = await self.join_voice_channel(channel)
        else:
            client = self.voice_client_in(msg.server)
            client.move_to(channel)

        notifier = asyncio.Event()

        player = client.create_ffmpeg_player(f'{sound_dir}/{sound}',
                                             options=f'-filter:a "atempo={speed/100}"' if speed != 100 else None,
                                             after=lambda: notifier.set())
        player.volume = volume / 100
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
            except (IndexError, KeyError):
                await self.send_message(msg.channel, 'Link or attachment required.')

        # Download file
        log.debug(f'Downloading from "{link}".')
        async with aiohttp.ClientSession() as session:
            async with session.get(link) as resp:
                if resp.status == 200:

                    # Write response to temporary file and moves it to the /sounds directory when done.
                    # Filename = blake2 hash of file
                    hash = hashlib.blake2b()
                    with open(f'{os.getcwd()}/tempsound', 'wb') as f:
                        while True:
                            chunk = await resp.content.read(1024)
                            if not chunk:
                                break
                            hash.update(chunk)
                            f.write(chunk)

                    filename = hash.hexdigest().upper()
                    log.debug(f'File hash is "{filename}"')

                    try:
                        os.rename(f'{os.getcwd()}/tempsound', f'{sound_dir}/{filename}')

                        self.sounds[name] = filename
                        await self.send_message(msg.channel, f'Saved **{name}**.')
                        self._update_json()
                    except FileExistsError:
                        await self.send_message(msg.channel, f'Sound already exists.')
                        log.debug(f'File with hash "{filename}" already exists. Aborting.')
                        log.info(
                            f'{msg.author.username} ({msg.server.name}) added "{name}" from "{link}".')

                else:
                    await self.send_message(msg.channel, f'Error while downloading: {resp.status}: {resp.reason}.')
                    log.debug(f'Status {resp.status}: {resp.reason} from download. Aborting.')
                await resp.release()

    async def remove_sound(self, msg: discord.Message, name: str):
        if name not in self.sounds.keys():
            await self.send_message(msg.channel, f'Sound **{name}** does not exist.')
            return

        sound = self.sounds.pop(name)
        os.remove(f'{sound_dir}/{sound}')
        await self.send_message(msg.channel, f'Removed **{name}**.')
        self._update_json()
        log.info(f'{msg.author.username} ({msg.server.name}) removed "{name}".')

    async def rename_sound(self, msg: discord.Message, name: str, new_name: str):
        try:
            sound = self.sounds.pop(name)
        except KeyError:
            await self.send_message(msg.channel, f'Sound **{name}** does not exist.')
            return

        self.sounds[new_name] = sound
        await self.send_message(msg.channel, f'**{name}** renamed to **{new_name}**.')
        self._update_json()
        log.info(f'{msg.author.username} ({msg.server.name}) renamed "{name}" to "{new_name}".')

    async def help(self, msg: discord.Message):
        help_msg = (
            '```\n'
            '+------------------------+------------------------------------------+\n'
            '| Command                | Function                                 |\n'
            '+------------------------+------------------------------------------+\n'
            '| !<name> [vXX] [sYY]    | Play a sound at XX% volume and YY% speed |\n'
            '| +<name> <link>         | Add a new sound                          |\n'
            '| -<name>                | Remove a sound                           |\n'
            '| ~<name> <new_name>     | Rename a sound                           |\n'
            '| $list                  | Print a list of all sounds               |\n'
            '| $stop                  | Force stop sound playback                |\n'
            '| $help                  | Print this message                       |\n'
            '+------------------------+------------------------------------------+\n'
            '```'
        )

        await self.send_message(msg.channel, help_msg)

    async def list(self, msg: discord.Message):
        if len(self.sounds) == 0:
            message = 'No sounds yet. Add one with `+<name> <link>`!'
        else:
            sorted_sounds = sorted(self.sounds.keys())
            split = OrderedDict()
            for sound in sorted_sounds:
                first = sound[0].lower()
                if first not in 'abcdefghijklmnopqrstuvwxyz':
                    first = '#'
                if first not in split.keys():
                    split[first] = [sound]
                else:
                    split[first].append(sound)

            message = '**Sounds**\n'

            for letter, sounds in split.items():
                line = f'**`{letter}`**: {", ".join(sounds)}\n'
                message += line

        await self.send_message(msg.channel, message)

    async def stop(self, msg: discord.Message):
        if not self.is_voice_connected(msg.server):
            return
        client = self.voice_client_in(msg.server)
        await client.disconnect()
        log.info(f'{msg.author.username} ({msg.server.name}) stopped playback.')

    def _update_json(self):
        with open('sounds.json', 'w') as f:
            json.dump(self.sounds, f)


def main():
    log.debug('Initializing Soundbot...')
    bot = SoundBot()

    log.debug('Loading token...')
    with open('token.txt', 'r') as f:
        token = f.read()

    log.info('Starting bot...')
    bot.run(token)
