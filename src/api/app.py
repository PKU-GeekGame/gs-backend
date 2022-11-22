from sanic import Sanic
import os
import asyncio
import logging
from sanic.request import Request
from sanic import response, HTTPResponse, Blueprint
from sanic.exceptions import SanicException
import httpx
from typing import Optional, Any

from . import get_cur_user
from ..logic import Worker
from ..state import User
from .. import utils
from .. import secret

OAUTH_HTTP_TIMEOUT = 20

utils.fix_zmq_asyncio_windows()

def get_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        http2=True,
        proxies=secret.OAUTH_HTTP_PROXIES,  # type: ignore
        timeout=OAUTH_HTTP_TIMEOUT,
    )

app = Sanic('guiding-star-backend')
app.config.DEBUG = False
app.config.OAS = False
app.config.PROXIES_COUNT = 1
app.config.KEEP_ALIVE_TIMEOUT = 15
app.config.REQUEST_MAX_SIZE = 1024*1024*(1+secret.WRITEUP_MAX_SIZE_MB)

app.ext.add_dependency(Worker, lambda req: req.app.ctx.worker)
app.ext.add_dependency(httpx.AsyncClient, lambda _req: get_http_client())
app.ext.add_dependency(Optional[User], get_cur_user)

@app.before_server_start
async def setup_game_state(cur_app: Sanic, _loop: Any) -> None:
    logging.getLogger('sanic.root').setLevel(logging.INFO)

    worker = Worker(cur_app.config.get('WORKER_NAME', f'worker-{os.getpid()}'), receiving_messages=True)
    cur_app.ctx.worker = worker
    await worker._before_run()
    cur_app.ctx._worker_task = asyncio.create_task(worker._mainloop())

async def handle_error(req: Request, exc: Exception) -> HTTPResponse:
    if isinstance(exc, SanicException):
        raise exc

    try:
        user = get_cur_user(req)
        debug_info = f'{req.id} {req.uri_template} U#{"--" if user is None else user._store.id}'
    except Exception as e:
        debug_info = f'no debug info, {repr(e)}'

    req.app.ctx.worker.log('error', 'app.handle_error', f'exception in request ({debug_info}): {utils.get_traceback(exc)}')
    return response.html(
        '<!doctype html>'
        '<h1>🤡 500 — Internal Server Error</h1>'
        '<p>This accident is recorded.</p>'
        f'<p>If you believe there is a bug, tell admin about this request ID: {req.id}</p>'
        '<br>'
        '<p>😭 <i>Project Guiding Star</i></p>',
        status=500
    )

app.error_handler.add(Exception, handle_error)

from .endpoint import auth
from .endpoint import wish
from .endpoint import template
from .endpoint import ws
from .endpoint import attachment
from .endpoint import sybil
svc = Blueprint.group(auth.bp, wish.bp, template.bp, ws.bp, attachment.bp, sybil.bp, url_prefix='/service')
app.blueprint(svc)

def start(idx0: int, worker_name: str) -> None:
    app.config.WORKER_NAME = worker_name
    app.run(**secret.WORKER_API_SERVER_KWARGS(idx0), workers=1) # type: ignore