from sanic import Blueprint, HTTPResponse, Request, response

from .. import store_anticheat_log

bp = Blueprint('sybil', url_prefix='/anticheat')

@bp.route('/report', methods=['POST'])
def recv_sybil_report(req: Request) -> HTTPResponse:
    fp = {
        'frontend': req.json,
        'http': {
            'language': req.headers.get('Accept-Language', None),
            'user_agent': req.headers.get('User-Agent', None),
        }
    }

    store_anticheat_log(req, ['sybil_report', fp])
    return response.text('OK')