from dataclasses import dataclass

import httpx
from sanic import Blueprint, Request, HTTPResponse, response
from sanic_ext import validate
from typing import Optional

from ..auth import auth_response, AuthResponse, AuthError, oauth2_redirect, oauth2_check_state
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

@bp.route('/manual')
@validate(query=AuthManualParam)
@auth_response
async def auth_manual(_req: Request, query: AuthManualParam, _worker: Worker) -> AuthResponse:
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

    return su_user

@bp.route('/github/login')
async def auth_github_req(req: Request) -> HTTPResponse:
    return oauth2_redirect(
        'https://github.com/login/oauth/authorize',
        secret.GITHUB_APP_ID,
        req.app.url_for('auth.auth_github_res', _external=True, _scheme=secret.BACKEND_SCHEME, _server=secret.BACKEND_HOSTNAME),
    )

@bp.route('/github/login/callback')
@auth_response
async def auth_github_res(req: Request, http_client: httpx.AsyncClient) -> AuthResponse:
    oauth2_check_state(req)

    oauth_code = req.args.get('code', None)
    if not oauth_code:
        raise AuthError('OAuth登录失败')

    token_res = await http_client.post('https://github.com/login/oauth/access_token', params={
        'client_id': secret.GITHUB_APP_ID,
        'client_secret': secret.GITHUB_APP_SECRET,
        'code': oauth_code,
    }, headers={
        'Accept': 'application/json',
    })
    token = token_res.json()['access_token']

    info_res = await http_client.get('https://api.github.com/user', headers={
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
    })
    info = info_res.json()

    uid = info.get('id', None)

    return f'github:{uid}', {'type': 'github', 'info': info, 'access_token': token}, 'other'