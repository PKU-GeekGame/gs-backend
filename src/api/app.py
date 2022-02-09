from sanic import Sanic
import os
import asyncio
from sanic.request import Request
from sanic import response, HTTPResponse, Blueprint
from sanic.exceptions import SanicException
from typing import Optional, Any

from ..logic import Worker
from ..state import User
from .. import utils

utils.fix_zmq_asyncio_windows()

app = Sanic('guiding-star-backend')
app.config.DEBUG = False
app.config.OAS = False
app.config.KEEP_ALIVE_TIMEOUT = 60

def get_cur_user(req: Request) -> Optional[User]:
    user = None

    game = req.app.ctx.worker.game
    if game is None:
        req.app.ctx.worker.log('warning', 'app.get_cur_user', 'game is not available, skipping user detection')
    else:
        auth_token = req.cookies.get('auth_token', None)
        if auth_token is not None:
            user = game.users.user_by_auth_token.get(auth_token, None)
            if user is not None and user.check_login() is not None:
                # user not allowed to log in
                user = None

    return user

app.ext.add_dependency(Worker, lambda req: req.app.ctx.worker)
app.ext.add_dependency(Optional[User], get_cur_user)

@app.before_server_start
async def setup_game_state(cur_app: Sanic, _loop: Any) -> None:
    worker = Worker(f'worker-{os.getpid()}')
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
svc = Blueprint.group(auth.bp, wish.bp, template.bp, url_prefix='/service')
app.blueprint(svc)