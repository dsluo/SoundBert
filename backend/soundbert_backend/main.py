from fastapi import FastAPI, APIRouter
from sqlalchemy.exc import DBAPIError
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse

from .routes import guilds, sounds, playbacks

app = FastAPI()


@app.exception_handler(DBAPIError)
async def database_error_handler(request: Request, exc: DBAPIError):
    return JSONResponse({"detail": str(exc.orig)}, status_code=status.HTTP_400_BAD_REQUEST)


router = APIRouter(prefix='/api')

router.include_router(guilds.router)
router.include_router(sounds.router)
router.include_router(playbacks.router)

app.include_router(router)
