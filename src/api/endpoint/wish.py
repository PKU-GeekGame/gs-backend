from sanic import Blueprint, Request
from sanic_ext import validate
from dataclasses import dataclass
import time
from typing import Optional, Dict, Any

from ..wish import wish_endpoint
from ...state import User
from ...logic import Worker, glitter
from ...store import UserProfileStore

bp = Blueprint('endpoint', url_prefix='/wish')

def group_disp(g: str) -> str:
    return {
        'pku': '北京大学',
        'other': '校外选手',
        'staff': '工作人员',
        'banned': '已封禁',
    }.get(g, f'({g})')

@wish_endpoint(bp, '/game_info')
async def game_info(_req: Request, _worker: Worker, user: Optional[User]) -> Dict[str, Any]:
    return {
        'user': None if user is None else {
            'id': user._store.id,
            'group': user._store.group,
            'group_disp': group_disp(user._store.group),
            'token': user._store.token,
            'profile': {
                field: (
                    getattr(user._store.profile, f'{field}_or_null') or ''
                ) for field in UserProfileStore.PROFILE_FOR_GROUP.get(user._store.group, [])
            },
            'terms_agreed': user._store.terms_agreed,
        },
        'feature': {
            'push': True,
            'game': user is not None,
        },
    }

@dataclass
class UpdateProfileParam:
    profile: Dict[str, str]

@wish_endpoint(bp, '/update_profile')
@validate(json=UpdateProfileParam)
async def update_profile(_req: Request, body: UpdateProfileParam, worker: Worker, user: Optional[User]) -> Dict[str, Any]:
    if user is None:
        return {'error': 'NO_USER', 'error_msg': '未登录'}

    if 1000*time.time()-user._store.profile.timestamp_ms < 1000:
        return {'error': 'RATE_LIMIT', 'error_msg': '请求太频繁'}

    err = user.check_update_profile()
    if err is not None:
        return {'error': err[0], 'error_msg': err[1]}

    required_fields = user._store.profile.PROFILE_FOR_GROUP.get(user._store.group, [])
    profile = {}
    for field in required_fields:
        if field not in body.profile:
            return {'error': 'INVALID_PARAM', 'error_msg': f'缺少 {field} 信息'}
        profile[field] = str(body.profile[field])

    rep = await worker.perform_action(glitter.UpdateProfileReq(
        client=worker.process_name,
        uid=user._store.id,
        profile=profile,
    ))
    if rep.error_msg is not None:
        return {'error': 'REDUCER_ERROR', 'error_msg': rep.error_msg}

    return {}

@wish_endpoint(bp, '/agree_term')
async def agree_term(_req: Request, worker: Worker, user: Optional[User]) -> Dict[str, Any]:
    if user is None:
        return {'error': 'NO_USER', 'error_msg': '未登录'}

    if user._store.terms_agreed:
        return {}

    rep = await worker.perform_action(glitter.AgreeTermReq(
        client=worker.process_name,
        uid=user._store.id,
    ))
    if rep.error_msg is not None:
        return {'error': 'REDUCER_ERROR', 'error_msg': rep.error_msg}

    return {}

@wish_endpoint(bp, '/announcements')
async def announcements(_req: Request, worker: Worker) -> Dict[str, Any]:
    if worker.game is None:
        return {'error': 'NO_GAME', 'error_msg': '服务暂时不可用'}

    return {
        'list': [{
            'id': ann._store.id,
            'title': ann.title,
            'timestamp_s': ann.timestamp_s,
            'content': ann.content,
        } for ann in worker.game.announcements.list],
    }

@wish_endpoint(bp, '/triggers')
async def triggers(_req: Request, worker: Worker) -> Dict[str, Any]:
    if worker.game is None:
        return {'error': 'NO_GAME', 'error_msg': '服务暂时不可用'}

    return {
        'current': worker.game.cur_tick,
        'list': [{
            'timestamp_s': trigger.timestamp_s,
            'name': trigger.name,
            'status': 'prs' if trigger.tick==worker.game.cur_tick else 'ftr' if trigger.tick>worker.game.cur_tick else 'pst',
        } for trigger in worker.game.trigger._stores]
    }

@wish_endpoint(bp, '/game')
async def get_game(_req: Request, worker: Worker, user: Optional[User]) -> Dict[str, Any]:
    if user is None:
        return {'error': 'NO_USER', 'error_msg': '未登录'}

    err = user.check_play_game()
    if err is not None:
        return {'error': err[0], 'error_msg': err[1]}

    return {}