from sanic import Blueprint, HTTPResponse, Request, response

from .. import store_anticheat_log
from .. import secret

bp = Blueprint('sybil', url_prefix='/anticheat')

@bp.route('/report', methods=['POST'])
def recv_sybil_report(req: Request) -> HTTPResponse:
    fp = {
        'frontend': req.json,
        'http': {
            'language': req.headers.get('Accept-Language', None),
            'user_agent': req.headers.get('User-Agent', None),
            'encoding': req.headers.get('Accept-Encoding', None),
        },
    }

    store_anticheat_log(req, ['sybil_report', fp])

    res = response.text('OK')

    ac_canary = req.cookies.get('anticheat_canary', None)
    if ac_canary:
        res.add_cookie('anticheat_canary', ac_canary, samesite='None', max_age=86400*30, domain=secret.BACKEND_HOSTNAME, secure=secret.BACKEND_SCHEME=='https')

    return res

@bp.route('/event', methods=['POST'])
def recv_sybil_event(req: Request) -> HTTPResponse:
    event = req.args.get('name')
    if event not in ['focus', 'blur', 'paste', 'visit_action']:
        return response.text('bad event', status=404)

    store_anticheat_log(req, ['event', event, req.json])
    return response.text('OK')