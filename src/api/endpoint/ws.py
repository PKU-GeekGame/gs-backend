from sanic import Blueprint, Request
from sanic.server.websockets.impl import WebsocketImplProtocol
import json

from .. import get_cur_user

bp = Blueprint('ws', url_prefix='/ws')

@bp.websocket('/push')
async def push(req: Request, ws: WebsocketImplProtocol) -> None:
    # xxx: cannot use dependency injection in websocket handlers
    # see https://github.com/sanic-org/sanic-ext/issues/61
    worker = req.app.ctx.worker
    user = get_cur_user(req)

    worker.log('debug', 'api.ws.push', f'got connection from {user}')

    if user is None:
        await ws.close(code=4337, reason='未登录')
        return

    chk = user.check_play_game()
    if chk is not None:
        await ws.close(code=4337, reason=chk[1])
        return

    message_id = worker.next_message_id
    while True:
        async with worker.message_cond:
            await worker.message_cond.wait_for(lambda: message_id<worker.next_message_id)

            while message_id<worker.next_message_id:
                pack = worker.local_messages.get(message_id, None)
                if pack is not None:
                    groups, msg = pack
                    if groups is None or user._store.group in groups:
                        await ws.send(json.dumps(msg))
                message_id += 1