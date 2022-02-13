from dataclasses import dataclass
from sanic import Blueprint, Request, HTTPResponse, response
from typing import Optional

from ..auth import auth_endpoint, AuthResponse, AuthError
from ...state import User
from ...logic import Worker
from ... import secret

bp = Blueprint('auth', url_prefix='/auth')

@bp.route('/logout')
async def auth_logout(_req: Request) -> HTTPResponse:
    res = response.redirect(secret.FRONTEND_PORTAL_URL)
    del res.cookies['auth_token'] # type: ignore
    return res

@dataclass
class AuthManualParam:
    identity: str

@auth_endpoint(bp, '/manual', AuthManualParam)
async def auth_manual(_req: Request, query: AuthManualParam, _worker: Worker) -> AuthResponse:
    return f'manual:{query.identity}', {}, 'staff'

@dataclass
class AuthSuParam:
    uid: int

@auth_endpoint(bp, '/su', AuthSuParam)
async def auth_su(_req: Request, query: AuthSuParam, worker: Worker, user: Optional[User]) -> AuthResponse:
    if user is None or not secret.IS_ADMIN(user._store):
        raise AuthError('没有权限')

    su_user = worker.game.users.user_by_id.get(query.uid, None)
    if su_user is None:
        raise AuthError('用户不存在')

    return su_user