from sanic import Blueprint, Request, HTTPResponse, response
from sanic.models.handler_types import RouteHandler
from functools import wraps
from inspect import isawaitable
from typing import Callable, Dict, Any, Union, Awaitable, List, Optional

ACCEPTED_WISH_VERS = ['2024.v2']

WishHandler = Callable[..., Union[Dict[str, Any], Awaitable[Dict[str, Any]]]]

def wish_endpoint(bp: Blueprint, uri: str, *, methods: Optional[List[str]] = None) -> Callable[[WishHandler], RouteHandler]:
    if methods is None:
        methods = ['POST']

    def decorator(fn: WishHandler) -> RouteHandler:
        @wraps(fn)
        async def wrapped(req: Request, *args: Any, **kwargs: Any) -> HTTPResponse:
            v = req.headers.get('X-Wish-Version', '(none)')
            if v not in ACCEPTED_WISH_VERS:
                return response.json({
                    'error': 'WISH_VERSION_MISMATCH',
                    'error_msg': f'比赛平台前端版本（{v}）需要更新',
                })

            retval_ = fn(req, *args, **kwargs)
            retval = (await retval_) if isawaitable(retval_) else retval_

            return response.json({
                'error': None, # may be overridden by retval
                **retval,
            })

        return bp.route(uri, methods, unquote=True)(wrapped)

    return decorator