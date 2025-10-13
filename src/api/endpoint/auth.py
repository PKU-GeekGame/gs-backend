from dataclasses import dataclass
from sanic import Blueprint, Request, HTTPResponse, response
from sanic_ext import validate
from typing import Optional

from ..auth import auth_response, AuthResponse, AuthError, oauth2_redirect, oauth2_check_state, del_cookie
from ...state import User
from ...store import UserStore
from ...logic import Worker
from ... import secret

bp = Blueprint('auth', url_prefix='/auth')

@bp.route('/logout')
async def auth_logout(_req: Request, user: Optional[User]) -> HTTPResponse:
    res = response.redirect(secret.BUILD_LOGIN_FINISH_URL(None, False))
    del_cookie(res, 'auth_token')
    if user and secret.IS_ADMIN(user._store):
        del_cookie(res, 'admin_2fa', path=secret.ADMIN_URL)
    return res

if secret.MANUAL_AUTH_ENABLED:
    @dataclass
    class AuthManualParam:
        identity: str

    @bp.route('/manual')
    @validate(query=AuthManualParam)
    @auth_response
    async def auth_manual(_req: Request, query: AuthManualParam, _worker: Worker) -> AuthResponse:
        if not secret.MANUAL_AUTH_ENABLED: # impossible, but add a fail safe here
            raise AuthError('手动登录已禁用')

        return f'manual:{query.identity}', {'type': 'manual'}, 'staff'

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
    token: str

@bp.route('/token')
@validate(query=AuthTokenParam)
@auth_response
async def auth_token(_req: Request, query: AuthTokenParam, worker: Worker) -> AuthResponse:
    if worker.game is None:
        raise AuthError('服务暂时不可用')

    user = worker.game.users.user_by_auth_token.get(query.token, None)
    if user is None:
        raise AuthError('密码错误')

    return user


@dataclass
class AuthPasswordParam:
    email: str
    password: str

@bp.post('/password')
@validate(form=AuthPasswordParam)
@auth_response
async def auth_password(_req: Request, body: AuthPasswordParam, worker: Worker) -> AuthResponse:
    if worker.game is None:
        raise AuthError('服务暂时不可用')

    user = worker.game.users.user_by_login_key.get(f'email:{body.email}', None)
    if user is None:
        raise AuthError('用户不存在或者密码错误')

    pw = user._store.login_properties.get('password', None)
    if pw is None or pw != body.password:
        raise AuthError('用户不存在或者密码错误')

    return user
