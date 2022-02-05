from dataclasses import dataclass
from sanic import Blueprint, response, Request, HTTPResponse
from sanic_ext import validate

from ..logic import Worker, glitter
from ..state import User

bp = Blueprint('auth', url_prefix='/auth')

URL_AFTER_LOGIN = '/'
LOGIN_MAX_AGE_S = 86400*30

def login(user: User) -> HTTPResponse:
    res = response.redirect(URL_AFTER_LOGIN)
    res.cookies['auth_token'] = user._store.auth_token
    res.cookies['auth_token']['httponly'] = True
    res.cookies['auth_token']['max-age'] = LOGIN_MAX_AGE_S
    return res

async def register_or_login(worker: Worker, type: str, identity: str, properties: dict, group: str) -> HTTPResponse:
    user = worker.game.users.user_by_login_key.get((type, identity))

    if user is None:  # reg new user
        rep = await worker.perform_action(glitter.RegUserReq(
            client=worker.process_name,
            login_type=type,
            login_identity=identity,
            login_properties=properties,
            group=group,
        ))
        if rep.error_msg is None:
            user = worker.game.users.user_by_login_key.get((type, identity))
            assert user is not None, 'user should be created'
        else:
            return response.text(f'Error: {rep.error_msg}')

    return login(user)

@dataclass
class AuthManualParam:
    identity: str

@bp.route('/manual')
@validate(query=AuthManualParam)
async def auth_manual(_req: Request, query: AuthManualParam, worker: Worker) -> HTTPResponse:
    return await register_or_login(worker, 'manual', query.identity, {}, 'staff')