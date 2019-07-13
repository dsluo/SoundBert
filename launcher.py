import asyncio
import logging

import click
import toml

import soundbert


@click.group()
def cli():
    pass


@cli.command()
@click.option('--config', 'config_path', default='./settings.toml', help='Path to config file.')
def run(config_path):

    # load config
    with open(config_path, 'r') as f:
        config = toml.load(f)

    # set up logging
    log_level = config['logging']['level']
    log_level = getattr(logging, log_level.upper(), None)
    if not isinstance(log_level, int):
        raise ValueError('Invalid log level')

    logging.basicConfig()
    log = logging.getLogger('soundbert')
    log.setLevel(log_level)

    # run bot
    token = config['bot'].pop('token')
    bot = soundbert.SoundBert(config)
    bot.run(token)


if __name__ == '__main__':
    try:
        import uvloop

        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ImportError:
        pass

    cli()
