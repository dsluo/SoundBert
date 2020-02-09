import argparse
import logging
import sys
from pathlib import Path

from alembic.config import Config as AlembicConfig, CommandLine

from .config import Config
from .soundbert import SoundBert

log = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description='A discord bot that play sounds.')
subparsers = parser.add_subparsers(dest='action')
run_parser = subparsers.add_parser('run', help='Run the bot.')
migrate_parser = subparsers.add_parser('migrate', help='Run database migrations for the bot.')
migrate_parser.add_argument(
        'alembic_args',
        nargs=argparse.REMAINDER,
        help='Arguments to pass to alembic. Alembic config location is ignored.'
)


def main():
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    config = Config.from_env()
    log_level = getattr(logging, config.log_level)
    if not isinstance(log_level, int):
        log.critical('Invalid log level.')
        sys.exit(1)
    log.setLevel(log_level)

    if args.action == 'run':
        run(config)
    else:
        migrate(args.alembic_args)


def run(config):
    bot = SoundBert(config)
    bot.run()


def migrate(args):
    alembic_command_line = CommandLine()
    options = alembic_command_line.parser.parse_args(args)
    if not hasattr(options, "cmd"):
        # see http://bugs.python.org/issue9253, argparse
        # behavior changed incompatibly in py3.3
        alembic_command_line.parser.error("too few arguments")
    else:
        alembic_ini = Path(__file__).parent / 'alembic.ini'
        cfg = AlembicConfig(
                file_=str(alembic_ini),
                ini_section=options.name,
                cmd_opts=options,
        )
        alembic_command_line.run_cmd(cfg, options)
