import logging
import sys

from .config import Config
from .soundbert import SoundBert

log = logging.getLogger(__name__)

def main():
    logging.basicConfig(level=logging.WARNING)

    config = Config.from_env()

    log_level = getattr(logging, config.log_level)
    if not isinstance(log_level, int):
        log.critical('Invalid log level.')
        sys.exit(1)
    log.setLevel(log_level)

    bot = SoundBert(config)
    bot.run()
