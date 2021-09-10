import uvicorn

from . import settings, app

if __name__ == '__main__':

    reload = settings.ENVIRONMENT == 'development'

    uvicorn.run(app)
