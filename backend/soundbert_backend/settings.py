from decouple import config, Choices

ENVIRONMENT = config('ENVIRONMENT', cast=Choices(['development', 'staging', 'production']))
DATABASE_URL = config('DB_URL')
DEFAULT_PREFIX = config('DEFAULT_PREFIX', '!')
