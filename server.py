"""The IJsbaan-klok on a Mac: the page, and the game's questions and answers with Apple's on-device model reading the
child's spelling."""

from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

import tutor
from play import handle

__all__ = ["app"]

PORT = 8740
PAGE = Path(__file__).parent / "static" / "index.html"


async def page(request: Request) -> FileResponse:
    return FileResponse(PAGE)


async def api(request: Request) -> JSONResponse:
    return JSONResponse(await handle(request.path_params["name"], await request.json(), tutor.spell))


app = Starlette(routes=[Route("/", page), Route("/{name}", api, methods=["POST"])])

if __name__ == "__main__":
    print(f"IJsbaan-klok: http://localhost:{PORT}")
    uvicorn.run(app, host="127.0.0.1", port=PORT)
