from sanic import Sanic
import os
import asyncio
from sanic.request import Request
from sanic import response
from typing import Optional, Any

from . import auth
from ..logic import Worker
from ..state import Game, User
from .. import utils
from .. import secret

utils.fix_zmq_asyncio_windows()

app = Sanic('guiding-star-backend')
app.config.DEBUG = secret.API_DEBUG_MODE
app.config.KEEP_ALIVE_TIMEOUT = 60

def get_cur_user(req: Request) -> Optional[User]:
    user = None

    game = req.app.ctx.worker.game
    if game is None:
        req.app.ctx.worker.log('warning', 'app.get_cur_user', 'skipping user detection because game is not available')
    else:
        auth_token = req.cookies.get('auth_token', None)
        if auth_token is not None:
            user = game.users.user_by_auth_token.get(auth_token, None)

    return user

app.ext.add_dependency(Worker, lambda req: req.app.ctx.worker)
app.ext.add_dependency(Optional[User], get_cur_user)

@app.before_server_start
async def setup_game_state(cur_app: Sanic, _loop: Any) -> None:
    worker = Worker(f'worker-{os.getpid()}')
    cur_app.ctx.worker = worker
    await worker._before_run()
    cur_app.ctx._worker_task = asyncio.create_task(worker._mainloop())

@app.route('/')
async def index(_req: Request, user: Optional[User]) -> response.HTTPResponse:
    if user is None:
        return response.text('hello guest')
    else:
        return response.text(f'hello {user._store.login_type}:{user._store.login_identity} ({user._store.profile.nickname_or_null})')

app.blueprint(auth.bp)