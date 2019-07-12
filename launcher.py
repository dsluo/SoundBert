import asyncio

import click
import toml

from soundbert import SoundBert

try:
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass


@click.command()
@click.option('--config', 'config_path', default='./settings.toml', help='Path to config file.')
def run(config_path):
    with open(config_path, 'r') as f:
        config = toml.load(f)

    token = config['bot'].pop('token')
    bot = SoundBert(config)
    bot.run(token)


if __name__ == '__main__':
    run()
