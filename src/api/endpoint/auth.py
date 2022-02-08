from dataclasses import dataclass
from sanic import Blueprint, Request, HTTPResponse, response

from ..auth import auth_endpoint, AuthResponse
from ...logic import Worker
from ... import secret

bp = Blueprint('auth', url_prefix='/auth')

@bp.route('/logout')
async def auth_logout(_req: Request) -> HTTPResponse:
    res = response.redirect(secret.FRONTEND_PORTAL_URL)
    del res.cookies['auth_token']
    return res

@dataclass
class AuthManualParam:
    identity: str

@auth_endpoint(bp, '/manual', AuthManualParam)
async def auth_manual(_req: Request, query: AuthManualParam, worker: Worker) -> AuthResponse:
    return f'manual:{query.identity}', {}, 'staff'