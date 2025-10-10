from sanic import Blueprint, Request, HTTPResponse, response
from pathlib import Path
from typing import Callable, Dict, Any, Optional

from .. import store_anticheat_log
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

def gen_attachment(chall: Challenge, att: Dict[str, Any], user: User, log: Callable[[utils.LogLevel, str, str], None], force_regen: bool = False) -> Optional[str]:
    assert att['type']=='dyn_attachment'

    mod_path = secret.ATTACHMENT_PATH / att['module_path']
    cache_path = mod_path / '_cache' / f'{user._store.id}.bin'
    cache_url = f'{att["module_path"]}/_cache/{user._store.id}.bin'

    cache_path.parent.mkdir(exist_ok=True)
    if cache_path.is_file():
        if force_regen:
            cache_path.unlink()
        else:
            return cache_url
    if not mod_path.is_dir():
        log('error', 'api.attachment.gen_attachment', f'module path is not dir: {mod_path}')
        return None

    log('info', 'api.attachment.gen_attachment', f'generating attachment {chall._store.key}::{att["filename"]} for {user._store.id}')

    try:
        with utils.chdir(mod_path):
            gen_mod = utils.load_module(mod_path / 'gen.py')
            gen_fn: Callable[[User, Challenge], Path] = gen_mod.gen
            out_path = gen_fn(user, chall)
            assert isinstance(out_path, Path), f'gen_fn must return a Path, got {type(out_path)}'
            out_path = out_path.resolve()

        out_path.chmod(0o644)
        if cache_path.exists():
            log('warning', 'api.attachment.gen_attachment', f'cache path already exists (race condition?) at {cache_path}')
        else:
            cache_path.symlink_to(out_path)
    except Exception as e:
        log('error', 'api.attachment.get_attachment', f'error generating attachment for {chall} [{mod_path}]: {utils.get_traceback(e)}')
        return None
    else:
        return cache_url


@bp.route('/<ch_key:str>/<fn:str>', unquote=True)
async def get_attachment(req: Request, ch_key: str, user_in_cookie: Optional[User], fn: str) -> HTTPResponse:
    worker: Worker = req.app.ctx.worker
    if worker.game is None:
        return response.text('服务暂时不可用', status=403)

    usertoken = req.args.get('token', None)
    user = worker.game.users.user_by_token.get(usertoken, None) if usertoken else None
    if user is None:
        user = user_in_cookie
    if user is None:
        return response.text('Token无效', status=403)

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

    store_anticheat_log(req, ['download_attachment', chall._store.key, fn], user)

    if att['type']=='attachment':
        return await download_attachment(att["file_path"])

    elif att['type']=='dyn_attachment':
        att_url = gen_attachment(chall, att, user, worker.log)
        if att_url is None:
            return response.text('附件暂时不可用', status=500)
        else:
            return await download_attachment(att_url)


    else:
        worker.log('error', 'api.attachment.get_attachment', f'unknown attachment type: {att["type"]}')
        return response.text('附件暂时不可用', status=500)