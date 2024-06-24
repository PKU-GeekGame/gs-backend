from sanic import Sanic
import os
import asyncio
import time
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

app = Sanic('guiding-star-backend')
app.config.DEBUG = False
app.config.OAS = False
app.config.PROXIES_COUNT = 1
app.config.KEEP_ALIVE_TIMEOUT = 15
app.config.REQUEST_MAX_SIZE = 1024*1024*(1+secret.WRITEUP_MAX_SIZE_MB)

def get_worker(req: Request) -> Worker:
    return req.app.ctx.worker

def get_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        http2=True,
        proxies=secret.OAUTH_HTTP_PROXIES,  # type: ignore
        timeout=OAUTH_HTTP_TIMEOUT,
    )

app.ext.add_dependency(Worker, get_worker)
app.ext.add_dependency(httpx.AsyncClient, get_http_client)
app.ext.add_dependency(Optional[User], get_cur_user)

@app.before_server_start
async def setup_game_state(cur_app: Sanic[Any, Any], _loop: Any) -> None:
    logging.getLogger('sanic.root').setLevel(logging.INFO)

    worker = Worker(cur_app.config.get('GS_WORKER_NAME', f'worker-{os.getpid()}'), receiving_messages=True)
    cur_app.ctx.worker = worker
    await worker._before_run()
    cur_app.ctx._worker_task = asyncio.create_task(worker._mainloop())

    cur_app.ctx.startup_finished = time.time()

async def handle_error(req: Request, exc: Exception) -> HTTPResponse:
    if isinstance(exc, SanicException):
        raise exc

    try:
        user = get_cur_user(req)
        debug_info = f'{req.id} {req.uri_template} U#{"--" if user is None else user._store.id}'
    except Exception as e:
        debug_info = f'no debug info, {repr(e)}'

    # xxx: dependency injection is broken during startup
    # https://github.com/sanic-org/sanic-ext/issues/218
    if isinstance(exc, TypeError) and time.time() - getattr(req.app.ctx, 'startup_finished', 1e50) < 3:
        req.app.ctx.worker.log('warning', 'app.handle_error', f'exception in request during startup ({debug_info}): {utils.get_traceback(exc)}')
        return response.text('服务正在启动', status=502)
    else:
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
    app.config.GS_WORKER_NAME = worker_name # used by gs worker
    app.config.WORKER_NAME = worker_name # used (also may be changed!) by sanic logging

    host, port = secret.WORKER_API_SERVER_ADDR(idx0)
    app.run(
        host=host,
        port=port,
        debug=False,
        access_log=False, # nginx already does this. disabling sanic access log makes it faster.
        single_process=True
    )