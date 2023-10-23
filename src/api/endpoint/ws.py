from sanic import Blueprint, Request
from sanic.server.websockets.impl import WebsocketImplProtocol
import json
from collections import Counter
from websockets.protocol import CLOSED, CLOSING
from typing import Dict, Optional, List

from ...logic import Worker
from ...state import User
from .. import store_anticheat_log
from ... import secret

bp = Blueprint('ws', url_prefix='/ws')

MAX_DEVICES_PER_USER = 16

online_uids: Dict[int, int] = Counter()

@bp.websocket('/push')
async def push(req: Request, ws: WebsocketImplProtocol, worker: Worker, user: Optional[User]) -> None:
    if not secret.WS_PUSH_ENABLED:
        await ws.close(code=4337, reason='推送通知已禁用')
        return

    telemetry = worker.custom_telemetry_data

    worker.log('debug', 'api.ws.push', f'got connection from {user}')

    if user is None:
        await ws.close(code=4337, reason='未登录')
        return

    chk = user.check_play_game()
    if chk is not None:
        await ws.close(code=4337, reason=chk[1])
        return

    if online_uids[user._store.id]>=MAX_DEVICES_PER_USER:
        await ws.close(code=4337, reason='同时在线设备过多')
        return

    online_uids[user._store.id] += 1
    store_anticheat_log(req, ['ws_online'])

    telemetry['ws_online_uids'] = len(online_uids)
    telemetry['ws_online_clients'] = sum(online_uids.values())

    try:
        message_id = worker.next_message_id

        while True:
            async with worker.message_cond:
                await worker.message_cond.wait_for(lambda: message_id<worker.next_message_id)

                if ws.ws_proto.state in [CLOSED, CLOSING]:
                    return

                while message_id<worker.next_message_id:
                    msg = worker.local_messages.get(message_id, None)
                    message_id += 1

                    if msg is not None:
                        if msg.get('type', None)=='push':
                            payload = msg['payload']
                            groups: Optional[List[str]] = msg['togroups']

                            if groups is None or user._store.group in groups:
                                await ws.send(json.dumps(payload))

    finally:
        worker.log('debug', 'api.ws.push', f'disconnected from {user}')

        store_anticheat_log(req, ['ws_offline'])
        online_uids[user._store.id] -= 1
        if online_uids[user._store.id] == 0:
            del online_uids[user._store.id]

        telemetry['ws_online_uids'] = len(online_uids)
        telemetry['ws_online_clients'] = sum(online_uids.values())