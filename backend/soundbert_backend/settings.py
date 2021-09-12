import itertools
import os

from decouple import config, Choices

ENVIRONMENT = config('ENVIRONMENT', cast=Choices(['development', 'staging', 'production']))
DATABASE_URL = config('DB_URL')
DEFAULT_PREFIX = config('DEFAULT_PREFIX', '!')
STORAGE_PROVIDER = config('STORAGE_PROVIDER')
STORAGE_CONFIG = {
    option.lstrip('STORAGE_').lower(): config(option)
    for option in filter(
            lambda x: x.startswith('STORAGE_'),
            # force search in both config and environ
            itertools.chain(config.config.repository.data.keys(), os.environ)
    )
}
