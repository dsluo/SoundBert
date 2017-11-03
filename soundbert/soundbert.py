import json
import logging
import os

import asyncpg
from discord.ext import commands

from soundbert.cogs.soundboard import Sounds

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class SoundBert(commands.AutoShardedBot):
    def __init__(self,
                 command_prefix,
                 sound_dir,
                 db_uri,
                 **options):
        super().__init__(command_prefix, **options)

        if not os.path.isdir(sound_dir):
            os.mkdir(sound_dir)

        self.db_pool = self.loop.run_until_complete(asyncpg.create_pool(db_uri))

        self.add_cog(Sounds(sound_dir, self))


def main():
    with open('config.json', 'r') as f:
        config = json.load(f)

    token = config.pop('token')

    bot = SoundBert('!', **config)

    bot.run(token)
