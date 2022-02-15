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
        {
            'client_id': secret.GITHUB_APP_ID,
        },
        req.app.url_for('auth.auth_github_res', _external=True, _scheme=secret.BACKEND_SCHEME, _server=secret.BACKEND_HOSTNAME),
    )

@bp.route('/github/login/callback')
@auth_response
async def auth_github_res(req: Request, http_client: httpx.AsyncClient, worker: Worker) -> AuthResponse:
    oauth_code = req.args.get('code', None)
    if not oauth_code:
        raise AuthError('OAuth登录失败')

    oauth2_check_state(req)

    token_res = await http_client.post('https://github.com/login/oauth/access_token', params={
        'client_id': secret.GITHUB_APP_ID,
        'client_secret': secret.GITHUB_APP_SECRET,
        'code': oauth_code,
    }, headers={
        'Accept': 'application/json',
    })
    token = token_res.json().get('access_token', None)
    if token is None:
        worker.log('warning', 'api.auth.github', f'get access_token failed:\n{token_res.json()}')
        raise AuthError('GitHub Token不存在')

    info_res = await http_client.get('https://api.github.com/user', headers={
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
    })
    info = info_res.json()

    uid = info.get('id', None)
    if uid is None:
        worker.log('warning', 'api.auth.github', f'get user failed:\n{info}')
        raise AuthError('GitHub UID不存在')

    return f'github:{uid}', {
        'type': 'github',
        'info': info,
        'access_token': token
    }, 'other'

@bp.route('/microsoft/login')
async def auth_ms_req(req: Request) -> HTTPResponse:
    return oauth2_redirect(
        'https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize',
        {
            'client_id': secret.MS_APP_ID,
            'response_type': 'code',
            'response_mode': 'query',
            'scope': 'User.Read',
        },
        req.app.url_for('auth.auth_ms_res', _external=True, _scheme=secret.BACKEND_SCHEME, _server=secret.BACKEND_HOSTNAME),
    )

@bp.route('/microsoft/login/callback')
@auth_response
async def auth_ms_res(req: Request, http_client: httpx.AsyncClient, worker: Worker) -> AuthResponse:
    oauth_code = req.args.get('code', None)
    if not oauth_code:
        raise AuthError('OAuth登录失败')

    oauth2_check_state(req)

    token_res = await http_client.post('https://login.microsoftonline.com/consumers/oauth2/v2.0/token', data={
        'client_id': secret.MS_APP_ID,
        'client_secret': secret.MS_APP_SECRET,
        'code': oauth_code,
        'grant_type': 'authorization_code',
        'scope': 'User.Read',
        'redirect_uri': req.app.url_for('auth.auth_ms_res', _external=True, _scheme=secret.BACKEND_SCHEME, _server=secret.BACKEND_HOSTNAME),
    })
    token_json = token_res.json()
    token = token_json.get('access_token', None)
    refresh_token = token_json.get('refresh_token', None)
    if token is None:
        worker.log('warning', 'api.auth.ms', f'get access_token failed:\n{token_json}')
        raise AuthError('MS Token不存在')

    info_res = await http_client.get('https://graph.microsoft.com/v1.0/me', headers={
        'Authorization': f'Bearer {token}',
    })
    info = info_res.json()

    uid = info.get('id', None)
    if uid is None:
        worker.log('warning', 'api.auth.ms', f'get user failed:\n{info}')
        raise AuthError('MS UID不存在')

    return f'ms:{uid}', {
        'type': 'microsoft',
        'info': info,
        'access_token': token,
        'refresh_token': refresh_token
    }, 'other'