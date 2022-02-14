from sanic.request import Request
from typing import Optional

from ..state import User

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