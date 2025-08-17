from sanic import Sanic
import os
import asyncio
import logging
from sanic.request import Request
from sanic import response, HTTPResponse, Blueprint
from sanic.exceptions import SanicException
import httpx
from typing import Optional, Any

from . import get_cur_user, render_info
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
        mounts=secret.OAUTH_HTTP_MOUNTS,
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

async def handle_error(req: Request, exc: Exception) -> HTTPResponse:
    try:
        user = get_cur_user(req)
        debug_info = f'{req.id} {req.uri_template} U#{"--" if user is None else user._store.id}'
    except Exception as e:
        debug_info = f'{req.id}, no debug info, {repr(e)}'

    if isinstance(exc, SanicException):
        if exc.status_code==500:
            req.app.ctx.worker.log(
                'error', 'app.handle_error',
                f'http 500 in request ({debug_info})\ncontext={exc.context}\nextra={exc.extra}\n{utils.get_traceback(exc)}',
            )

        return response.html(render_info(
            title=f'🤡 HTTP Error {exc.status_code}',
            body=exc.message,
        ), status=exc.status_code)

    # otherwise, 500

    req.app.ctx.worker.log('error', 'app.handle_error', f'exception in request ({debug_info})\n{utils.get_traceback(exc)}')

    return response.html(render_info(
        title='🤡 Internal Server Error',
        body=f'已记录日志，Request ID: {req.id}',
    ), status=500)

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