import logging

from .config import Config
from .soundbert import SoundBert

logging.basicConfig(level=logging.DEBUG)

if __name__ == '__main__':
    config = Config.from_env()
    bot = SoundBert(config)
    bot.run()