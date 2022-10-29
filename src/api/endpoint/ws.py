from sanic import Blueprint, Request
from sanic.server.websockets.impl import WebsocketImplProtocol
import json
from collections import Counter
from websockets.connection import CLOSED, CLOSING
from typing import Dict

from .. import get_cur_user

bp = Blueprint('ws', url_prefix='/ws')

online_uids: Dict[int, int] = Counter()

@bp.websocket('/push')
async def push(req: Request, ws: WebsocketImplProtocol) -> None:
    # xxx: cannot use dependency injection in websocket handlers
    # see https://github.com/sanic-org/sanic-ext/issues/61
    worker = req.app.ctx.worker
    user = get_cur_user(req)
    telemetry = worker.custom_telemetry_data

    worker.log('debug', 'api.ws.push', f'got connection from {user}')

    if user is None:
        await ws.close(code=4337, reason='未登录')
        return

    chk = user.check_play_game()
    if chk is not None:
        await ws.close(code=4337, reason=chk[1])
        return

    online_uids[user._store.id] += 1

    telemetry['ws_online_uids'] = len(online_uids)
    telemetry['ws_online_clients'] = sum(online_uids.values())

    try:
        message_id = worker.next_message_id

        while True:
            async with worker.message_cond:
                await worker.message_cond.wait_for(lambda: message_id<worker.next_message_id)

                if ws.connection.state in [CLOSED, CLOSING]:
                    return

                while message_id<worker.next_message_id:
                    pack = worker.local_messages.get(message_id, None)
                    if pack is not None:
                        groups, msg = pack
                        if msg.get('type', None)=='heartbeat_sent':
                            continue

                        if groups is None or user._store.group in groups:
                            await ws.send(json.dumps(msg))
                    message_id += 1

    finally:
        worker.log('debug', 'api.ws.push', f'disconnected from {user}')

        online_uids[user._store.id] -= 1
        if online_uids[user._store.id] == 0:
            del online_uids[user._store.id]

        telemetry['ws_online_uids'] = len(online_uids)
        telemetry['ws_online_clients'] = sum(online_uids.values())