from sanic import Blueprint, Request, HTTPResponse, response
import pathlib
from typing import Dict, Tuple

from ... import utils
from ...logic.worker import Worker

bp = Blueprint('template', url_prefix='/template')

FILES = [
    'game',
    'terms',
    'faq',
]
TEMPLATE_PATH = pathlib.Path('data/templates')
assert TEMPLATE_PATH.is_dir()

_cache: Dict[str, Tuple[int, str]] = {}

@bp.route('/<file:str>')
async def get_template(_req: Request, file: str, worker: Worker) -> HTTPResponse:
    if file not in FILES:
        return response.text('invalid template name', status=400)

    p = TEMPLATE_PATH/f'{file}.md'
    if not p.is_file():
        return response.text('template not found', status=404)

    ts = int(p.stat().st_mtime*1000)

    cache = _cache.get(file, None)
    if cache is not None and cache[0]==ts:
        return response.html(cache[1])
    else:
        worker.log('debug', 'api.template.get_template', f'rendering and caching {file}')
        with p.open('r', encoding='utf-8') as f:
            md = f.read()
        html = utils.render_template(md)

        _cache[file] = (ts, html)
        return response.html(html)
