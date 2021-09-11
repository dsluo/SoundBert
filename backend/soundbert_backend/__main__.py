import uvicorn

from .main import app
from . import settings

if __name__ == '__main__':

    reload = settings.ENVIRONMENT == 'development'

    uvicorn.run(app, reload=reload)
