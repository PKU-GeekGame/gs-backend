from dataclasses import dataclass
from sanic import Blueprint, Request, HTTPResponse, response
from sanic_ext import validate
from typing import Optional

from ..auth import auth_response, AuthResponse, AuthError
from ...state import User
from ...store import UserStore
from ...logic import Worker
from ... import secret

bp = Blueprint('auth', url_prefix='/auth')

@bp.route('/logout')
async def auth_logout(_req: Request) -> HTTPResponse:
    res = response.redirect(secret.FRONTEND_PORTAL_URL)
    del res.cookies['auth_token'] # type: ignore
    del res.cookies['admin_2fa'] # type: ignore
    return res

@dataclass
class AuthManualParam:
    identity: str
    group: str

@bp.route('/manual')
@validate(query=AuthManualParam)
@auth_response
async def auth_manual(_req: Request, query: AuthManualParam, _worker: Worker, user: Optional[User]) -> AuthResponse:
    if not secret.MANUAL_AUTH_ENABLED and not secret.IS_ADMIN(user._store):
        raise AuthError('手动登录已禁用')

    if query.group not in UserStore.GROUPS:
        raise AuthError('用户组不存在')

    return f'manual:{query.identity}', {'type': 'manual'}, query.group

@dataclass
class AuthSuParam:
    uid: int

@bp.route('/su')
@validate(query=AuthSuParam)
@auth_response
async def auth_su(_req: Request, query: AuthSuParam, worker: Worker, user: Optional[User]) -> AuthResponse:
    if user is None or not secret.IS_ADMIN(user._store):
        raise AuthError('没有权限')
    if worker.game is None:
        raise AuthError('服务暂时不可用')

    su_user = worker.game.users.user_by_id.get(query.uid, None)
    if su_user is None:
        raise AuthError('用户不存在')
    if secret.IS_ADMIN(su_user._store):
        raise AuthError('不能切换到管理员账号')

    return su_user

@dataclass
class AuthTokenParam:
    login_key: str
    token: str

@bp.route('/token')
@validate(query=AuthTokenParam)
@auth_response
async def auth_token(_req: Request, query: AuthTokenParam, worker: Worker) -> AuthResponse:
    if worker.game is None:
        raise AuthError('服务暂时不可用')

    user = worker.game.users.user_by_login_key.get(query.login_key, None)
    if user is None or user._store.token != query.token:
        raise AuthError('用户名或密码错误')

    return user
