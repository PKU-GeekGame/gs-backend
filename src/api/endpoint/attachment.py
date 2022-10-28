from sanic import Blueprint, Request, HTTPResponse, response
from pathlib import Path
from typing import Optional, Callable
import importlib.util
import shutil

from ...state import User, Challenge
from ...logic import Worker
from ... import utils
from ... import secret

bp = Blueprint('attachment', url_prefix='/attachment')

def load_module(module_path: Path) -> Callable[[User, Challenge], Path]:
    # https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
    spec = importlib.util.spec_from_file_location('_dyn_attachment', str(module_path / 'gen.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.gen

@bp.route('/<ch_key:str>/<fn:str>', unquote=True)
async def get_attachment(req: Request, ch_key: str, fn: str, worker: Worker, user: Optional[User]) -> HTTPResponse:
    if user is None:
        return response.text('未登录', status=403)
    if worker.game is None:
        return response.text('服务暂时不可用', status=403)

    err = user.check_play_game()
    if err is not None:
        return response.text(err[1], status=403)

    chall = worker.game.challenges.chall_by_key.get(ch_key, None)
    if chall is None or not chall.cur_effective:
        return response.text('题目不存在', status=404)

    att = chall.attachments.get(fn, None)
    if att is None:
        return response.text('附件不存在', status=404)

    if att['type']=='attachment':
        return response.raw('redirecting...', 200, content_type='', headers={
            'X-Accel-Redirect': f'{secret.ATTACHMENT_URL}/{att["file_path"]}',
        })

    elif att['type']=='dyn_attachment':
        mod_path = secret.ATTACHMENT_PATH / att['module_path']
        cache_path = mod_path / '_cache' / f'{user._store.id}.bin'
        cache_url = f'{secret.ATTACHMENT_URL}/{att["module_path"]}/_cache/{user._store.id}.bin'

        cache_path.parent.mkdir(exist_ok=True)
        if cache_path.is_file():
            return response.raw('redirecting...', 200, content_type='', headers={
                'X-Accel-Redirect': cache_url,
            })
        if not mod_path.is_dir():
            worker.log('error', 'api.attachment.get_attachment', f'module path is not dir: {mod_path}')
            return response.text('附件暂时不可用', status=500)

        worker.log('info', 'api.attachment.get_attachment', f'generating attachment {chall._store.key}::{att["filename"]} for {user._store.id}')

        try:
            gen_fn = load_module(mod_path)
            out_path = gen_fn(user, chall)
            assert isinstance(out_path, Path), f'gen_fn must return a Path, got {type(gen_fn)}'
            shutil.move(out_path, cache_path)
            cache_path.chmod(0o644)
        except Exception as e:
            worker.log('error', 'api.attachment.get_attachment', f'error generating attachment: {utils.get_traceback(e)}')
            return response.text('附件暂时不可用', status=500)
        else:
            return response.raw('redirecting...', 200, content_type='', headers={
                'X-Accel-Redirect': cache_url,
            })

    else:
        worker.log('error', 'api.attachment.get_attachment', f'unknown attachment type: {att["type"]}')
        return response.text('附件暂时不可用', status=500)