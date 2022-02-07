from sanic import Blueprint, response, Request, HTTPResponse
from sanic.models.handler_types import RouteHandler
from sanic_ext import validate
from html import escape
from functools import wraps
from inspect import isawaitable
from typing import Dict, Any, Callable, Tuple, Union, Awaitable, Type, Optional

from ..logic import Worker, glitter
from ..state import User
from .. import secret

LOGIN_MAX_AGE_S = 86400*30

AuthResponse = Union[str, Tuple[str, Dict[str, Any], str]] #
AuthHandler = Callable[..., Union[AuthResponse, Awaitable[AuthResponse]]]

def login(user: User) -> HTTPResponse:
    chk = user.check_login()
    if chk is not None:
        return response.text(chk)

    res = response.redirect(secret.FRONTEND_PORTAL_URL)
    res.cookies['auth_token'] = user._store.auth_token
    #res.cookies['auth_token']['samesite'] = 'None' # it requires secure
    res.cookies['auth_token']['max-age'] = LOGIN_MAX_AGE_S
    return res

class AuthError(Exception):
    def __init__(self, message: str):
        self.message: str = message

    def __str__(self) -> str:
        return self.message

async def register_or_login(worker: Worker, login_key: str, properties: Dict[str, Any], group: str) -> HTTPResponse:
    if worker.game is None:
        worker.log('warning', 'api.auth.register_or_login', 'game is not available')
        raise AuthError('后端服务暂时不可用')
    user = worker.game.users.user_by_login_key.get(login_key)

    if user is None:  # reg new user
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
            raise response.text(f'注册账户失败：{rep.error_msg}')

    return login(user)

def auth_endpoint(bp: Blueprint, uri: str, query: Optional[Type[Any]] = None) -> Callable[[AuthHandler], RouteHandler]:
    def decorator(fn: AuthHandler) -> RouteHandler:
        @wraps(fn)
        async def wrapped(req: Request, *args: Any, **kwargs: Any) -> HTTPResponse:
            retval_ = fn(req, *args, **kwargs)
            retval = (await retval_) if isawaitable(retval_) else retval_

            try:
                if isinstance(retval, str):
                    raise AuthError(retval)
                else:
                    login_key, properties, group = retval
                    return await register_or_login(req.app.ctx.worker, login_key, properties, group)
            except AuthError as e:
                return response.html(
                    '<!doctype html>'
                    '<h1>登录失败</h1>'
                    f'<p>{escape(e.message)}</p>'
                    '<br>'
                    f'<p><a href="{secret.FRONTEND_PORTAL_URL}">返回比赛平台</a></p>'
                )

        wrapped = validate(query=query)(wrapped)

        return bp.route(uri, ['GET'])(wrapped)

    return decorator