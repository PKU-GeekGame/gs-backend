from sanic import Blueprint, Request, HTTPResponse, response
from pathlib import Path
from typing import Optional, Callable

from .. import store_anticheat_log, get_cur_user
from ...state import User, Challenge
from ...logic import Worker
from ... import utils
from ... import secret

bp = Blueprint('attachment', url_prefix='/attachment')

async def download_attachment(p: str) -> HTTPResponse:
    if secret.ATTACHMENT_URL is not None: # use X-Accel-Redirect
        return response.raw('redirecting...', 200, content_type='', headers={
            'X-Accel-Redirect': f'{secret.ATTACHMENT_URL}/{p}',
        })
    else: # fallback to direct download
        return await response.file(
            secret.ATTACHMENT_PATH / p,
            headers={
                'Cache-Control': 'no-cache',
                'Content-Disposition': 'attachment',
            },
            mime_type='application/octet-stream',
        )


@bp.route('/<ch_key:str>/<fn:str>', unquote=True)
async def get_attachment(req: Request, ch_key: str, fn: str) -> HTTPResponse:
    worker: Worker = req.app.ctx.worker
    user: Optional[User] = get_cur_user(req)

    if user is None:
        return response.text('未登录', status=403)
    if worker.game is None:
        return response.text('服务暂时不可用', status=403)

    err = user.check_play_game()
    if err is not None:
        return response.text(err[1], status=403)

    is_admin = secret.IS_ADMIN(user._store)

    chall = worker.game.challenges.chall_by_key.get(ch_key, None)
    if chall is None or (not chall.cur_effective and not is_admin):
        return response.text('题目不存在', status=404)

    att = chall.attachments.get(fn, None)
    if att is None or (att['effective_after']>worker.game.cur_tick and not is_admin):
        return response.text('附件不存在', status=404)

    store_anticheat_log(req, ['download_attachment', chall._store.key, fn])

    if att['type']=='attachment':
        return await download_attachment(att["file_path"])

    elif att['type']=='dyn_attachment':
        mod_path = secret.ATTACHMENT_PATH / att['module_path']
        cache_path = mod_path / '_cache' / f'{user._store.id}.bin'
        cache_url = f'{att["module_path"]}/_cache/{user._store.id}.bin'

        cache_path.parent.mkdir(exist_ok=True)
        if cache_path.is_file():
            return await download_attachment(cache_url)
        if not mod_path.is_dir():
            worker.log('error', 'api.attachment.get_attachment', f'module path is not dir: {mod_path}')
            return response.text('附件暂时不可用', status=500)

        worker.log('info', 'api.attachment.get_attachment', f'generating attachment {chall._store.key}::{att["filename"]} for {user._store.id}')

        try:
            with utils.chdir(mod_path):
                gen_mod = utils.load_module(mod_path / 'gen.py')
                gen_fn: Callable[[User, Challenge], Path] = gen_mod.gen
                out_path = gen_fn(user, chall)
                assert isinstance(out_path, Path), f'gen_fn must return a Path, got {type(out_path)}'
                out_path = out_path.resolve()

            out_path.chmod(0o644)
            cache_path.symlink_to(out_path)
        except Exception as e:
            worker.log('error', 'api.attachment.get_attachment', f'error generating attachment: {utils.get_traceback(e)}')
            return response.text('附件暂时不可用', status=500)
        else:
            return await download_attachment(cache_url)

    else:
        worker.log('error', 'api.attachment.get_attachment', f'unknown attachment type: {att["type"]}')
        return response.text('附件暂时不可用', status=500)