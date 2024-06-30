import httpx
from sanic import response, Request, HTTPResponse
from sanic.models.handler_types import RouteHandler
from html import escape
from functools import wraps
from inspect import isawaitable
from urllib.parse import quote
from typing import Dict, Any, Callable, Tuple, Union, Awaitable

from . import store_anticheat_log
from ..logic import Worker, glitter
from ..state import User
from .. import secret
from .. import utils

LOGIN_MAX_AGE_S = 86400*30

AuthResponse = Union[User, Tuple[str, Dict[str, Any], str]]
AuthHandler = Callable[..., Union[AuthResponse, Awaitable[AuthResponse]]]

def add_cookie(res: HTTPResponse, name: str, value: str, path: str = '/', max_age: int = LOGIN_MAX_AGE_S) -> None:
    res.cookies.add_cookie(name, value, path=path, httponly=True, samesite='Lax', max_age=max_age, secure=secret.BACKEND_SCHEME=='https')

def del_cookie(res: HTTPResponse, name: str, path: str = '/') -> None:
    # xxx: cannot use `res.cookies.delete_cookie` here
    # https://github.com/sanic-org/sanic/issues/2972
    return add_cookie(res, name, '', path=path, max_age=0)

def _login(req: Request, worker: Worker, user: User) -> HTTPResponse:
    chk = user.check_login()
    if chk is not None:
        raise AuthError(chk[1])

    store_anticheat_log(req, ['login'])

    res = response.redirect(secret.FRONTEND_PORTAL_URL)

    add_cookie(res, 'auth_token', user._store.auth_token)
    if secret.IS_ADMIN(user._store):
        worker.log('warning', 'auth.login', f'sending admin 2fa cookie to U#{user._store.id}')
        add_cookie(res, 'admin_2fa', secret.ADMIN_2FA_COOKIE, secret.ADMIN_URL)

    del_cookie(res, 'oauth_state')
    return res

class AuthError(Exception):
    def __init__(self, message: str):
        self.message: str = message

    def __str__(self) -> str:
        return self.message

async def _register_or_login(req: Request, worker: Worker, login_key: str, properties: Dict[str, Any], group: str) -> HTTPResponse:
    if worker.game is None:
        worker.log('warning', 'api.auth.register_or_login', 'game is not available')
        raise AuthError('服务暂时不可用')
    user = worker.game.users.user_by_login_key.get(login_key)

    if user is None:  # reg new user
        if not secret.REGISTRATION_ENABLED:
            raise AuthError('目前不允许注册新账户')

        rep = await worker.perform_action(glitter.RegUserReq(
            client=worker.process_name,
            login_key=login_key,
            login_properties=properties,
            group=group,
        ))

        if rep.error_msg is None:
            user = worker.game.users.user_by_login_key.get(login_key)
            assert user is not None, 'user should be created'
        else:
            raise AuthError(f'注册账户失败：{rep.error_msg}')

    return _login(req, worker, user)

def auth_response(fn: AuthHandler) -> RouteHandler:
    @wraps(fn)
    async def wrapped(req: Request, *args: Any, **kwargs: Any) -> HTTPResponse:
        worker = req.app.ctx.worker
        try:
            try:
                retval_ = fn(req, *args, **kwargs)
                retval = (await retval_) if isawaitable(retval_) else retval_
                if isinstance(retval, User):
                    return _login(req, worker, retval)
                else:
                    login_key, properties, group = retval
                    return await _register_or_login(req, worker, login_key, properties, group)
            except httpx.RequestError as e:
                worker.log('warning', 'api.auth.auth_response', f'request error: {utils.get_traceback(e)}')
                raise AuthError('第三方服务网络错误')
        except AuthError as e:
            return response.html(
                '<!doctype html>'
                '<h1>登录失败</h1>'
                f'<p>{escape(e.message)}</p>'
                '<br>'
                f'<p><a href="{secret.FRONTEND_PORTAL_URL}">返回比赛平台</a></p>'
            )

    return wrapped

def build_url(url: str, query: Dict[str, str]) -> str:
    assert '?' not in url, 'url should not contain query string part'
    query_str = '&'.join(f'{quote(k)}={quote(v)}' for k, v in query.items())
    return f'{url}?{query_str}'

def oauth2_redirect(url: str, params: Dict[str, str], redirect_url: str) -> HTTPResponse:
    assert '://' in redirect_url, 'redirect url should be absolute'

    state = utils.gen_random_str(32)
    res = response.redirect(build_url(url, {
        **params,
        'redirect_uri': redirect_url,
        'state': state,
    }))

    add_cookie(res, 'oauth_state', state, max_age=600)
    return res

def oauth2_check_state(req: Request) -> None:
    state = req.cookies.get('oauth_state', None)
    if not state:
        raise AuthError('OAuth错误：state无效')
    if state!=req.args.get('state', None):
        raise AuthError('OAuth错误：state不匹配')