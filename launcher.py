import argparse
import json

from soundbert import SoundBert

parser = argparse.ArgumentParser()
parser.add_argument('config', type=argparse.FileType('r'))
args = parser.parse_args()

with args.config as f:
    config = json.load(f)

bot = SoundBert(config)

if __name__ == '__main__':
    bot.run()
