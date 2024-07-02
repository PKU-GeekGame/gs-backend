from sanic.request import Request
import json
import time
from typing import Optional, List, Any

from ..state import User
from .. import secret
from .. import utils

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

MAX_LINE_LEN = 32*1024

def store_anticheat_log(req: Request, data: List[Any]) -> None:
    if not secret.ANTICHEAT_RECEIVER_ENABLED:
        return

    user = get_cur_user(req)
    if user is not None:
        try:
            addr = req.remote_addr
            ac_canary = req.cookies.get('anticheat_canary', None)
            tab_id = req.args.get('tabid', None)

            encoded = json.dumps(
                [time.time(), addr, ac_canary, tab_id, *data],
                ensure_ascii=False,
            ).encode('utf-8')
            if len(encoded)>MAX_LINE_LEN:
                encoded = encoded[:MAX_LINE_LEN]

            with (secret.SYBIL_LOG_PATH / f'{user._store.id}.log').open('ab') as f:
                f.write(encoded + b'\n')

        except Exception as e:
            req.app.ctx.worker.log('error', 'app.store_anticheat_log', f'cannot write log for U#{user._store.id}: {utils.get_traceback(e)}')