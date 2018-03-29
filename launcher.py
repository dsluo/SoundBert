import argparse
import json
import logging
import time

from soundbert import SoundBert

parser = argparse.ArgumentParser()
parser.add_argument('config', type=argparse.FileType('r'))
parser.add_argument('--log')
args = parser.parse_args()

if args.log:
    logging.basicConfig(filename=args.log, level=logging.INFO)
else:
    logging.basicConfig(level=logging.INFO)

log = logging.getLogger(__name__)

config = json.load(args.config)
args.config.close()

if __name__ == '__main__':
    bot = SoundBert(config)

    while True:
        try:
            bot.run()
        except KeyboardInterrupt:
            log.info('Received Ctrl-C. Stopping...')
            break
        except Exception as ex:
            log.critical('Bot crashed: {0}', ex.args)
            time.sleep(5)  # kind of arbitrary
