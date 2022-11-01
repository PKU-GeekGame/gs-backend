from sanic import Blueprint, Request, HTTPResponse, response
import re
from typing import Dict, Tuple, Optional

from .. import store_anticheat_log
from ...logic.worker import Worker
from ...state import User
from ... import utils
from ... import secret

bp = Blueprint('template', url_prefix='/template')

TEMPLATE_PATH = secret.TEMPLATE_PATH
assert TEMPLATE_PATH.is_dir()

TEMPLATE_NAME_RE = re.compile(r'^[a-zA-Z0-9\-_]+$')

def etagged_response(req: Request, etag: str, html_body: str) -> HTTPResponse:
    etag = f'W/"{etag}"'

    req_etag = req.headers.get('If-None-Match', None)
    if req_etag==etag:
        return response.html('', status=304, headers={'ETag': etag})
    else:
        return response.html(html_body, headers={'ETag': etag})

_cache: Dict[Tuple[str, Optional[str], int], Tuple[int, str]] = {}

@bp.route('/<filename:str>')
async def get_template(req: Request, filename: str, worker: Worker, user: Optional[User]) -> HTTPResponse:
    if worker.game is None:
        return response.text('服务暂时不可用', status=403)

    if not TEMPLATE_NAME_RE.fullmatch(filename):
        return response.text('没有这个模板', status=404)

    p = TEMPLATE_PATH/f'{filename}.md'
    if not p.is_file():
        return response.text('没有这个模板', status=404)

    ts = int(p.stat().st_mtime*1000)

    store_anticheat_log(req, ['get_template', filename])

    group = None if user is None else user._store.group
    tick = worker.game.cur_tick
    cache_key = (filename, group, tick)

    cache = _cache.get(cache_key, None)
    if cache is not None and cache[0]==ts:
        return etagged_response(req, str(ts), cache[1])
    else:
        worker.log('debug', 'api.template.get_template', f'rendering and caching {cache_key}')
        with p.open('r', encoding='utf-8') as f:
            md = f.read()

        try:
            html = utils.render_template(md, {'group': group, 'tick': tick})
        except Exception as e:
            worker.log('error', 'api.template.get_template', f'template render failed: {filename}: {utils.get_traceback(e)}')
            return response.text('<i>（模板渲染失败）</i>')

        _cache[cache_key] = (ts, html)
        return etagged_response(req, str(ts), html)
