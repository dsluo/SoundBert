import asyncio
import logging
from datetime import datetime
from pathlib import Path

import asyncpg
import click
import toml

import soundbert


@click.group()
@click.option(
    '--config', 'config_path', default='./settings.toml', help='Path to config file.'
)
@click.pass_context
def cli(ctx, config_path):
    ctx.ensure_object(dict)

    # load config
    with open(config_path, 'r') as f:
        config = toml.load(f)
    ctx.obj['config'] = config

    # set up logging
    log_level = config['logging']['level']
    log_level = getattr(logging, log_level.upper(), None)
    if not isinstance(log_level, int):
        raise ValueError('Invalid log level')

    logging.basicConfig()
    log = logging.getLogger('soundbert')
    log.setLevel(log_level)

    ctx.obj['log'] = log


@cli.command()
@click.pass_obj
def run(obj):
    log: logging.Logger = obj['log']
    config = obj['config']

    # run bot
    log.info('Starting SoundBert.')
    token = config['bot'].pop('token')
    bot = soundbert.SoundBert(config)
    bot.run(token)
    log.info('Shutting down.')


@cli.command()
@click.pass_obj
def migrate(obj):
    log: logging.Logger = obj['log']
    config = obj['config']

    log.info('Migrating...')

    async def do_migration():
        conn = await asyncpg.connect(config['bot']['db_uri'])

        try:
            current = await conn.fetchval(
                'SELECT id FROM migrations ORDER BY id DESC LIMIT 1'
            )
            if current is None:
                current = 0
            log.debug(f'Currently at migration {current}.')
        except asyncpg.UndefinedTableError:
            await conn.execute("""
                CREATE TABLE migrations(
                    id INT CONSTRAINT migrations_pk PRIMARY KEY,
                    description TEXT,
                    applied TIMESTAMP NOT NULL
                );
            """)
            current = 0
            log.debug(f'Created migration table. Currently at migration {current}.')

        migrations = sorted(Path('migrations').glob('*.sql'), key=lambda x: x.name)

        applied = 0
        skipped = 0

        try:
            for migration in migrations:
                id, description = migration.stem.split('_', maxsplit=1)
                id = int(id)
                if id <= current:
                    log.debug(f'Skipping migration {id}: {description}.')
                    continue

                with migration.open('r') as f:
                    sql = f.read()

                async with conn.transaction():
                    await conn.execute(sql)
                    await conn.execute('INSERT INTO migrations VALUES ($1, $2, $3)', id, description, datetime.now())
                log.debug(f'Applied migration {id}: {description}.')
        except asyncpg.PostgresError:
            log.exception(f'Error executing migration {id}: {description}.')
        else:
            log.info(f'Applied {applied} and skipped {skipped} migrations.')
        finally:
            await conn.close()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(do_migration())


if __name__ == '__main__':
    try:
        import uvloop

        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ImportError:
        pass

    cli()
