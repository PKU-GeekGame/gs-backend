from sanic import Blueprint, Request
from sanic.request import File
from sanic_ext import validate
from dataclasses import dataclass
import time
import json
import re
import hashlib
from typing import Optional, Dict, Any, List, Tuple

from ..wish import wish_endpoint
from ...state import User, ScoreBoard, Submission
from ...logic import Worker, glitter
from ...store import UserProfileStore, ChallengeStore
from ... import secret

bp = Blueprint('wish', url_prefix='/wish')

@wish_endpoint(bp, '/game_info')
async def game_info(_req: Request, _worker: Worker, user: Optional[User]) -> Dict[str, Any]:
    return {
        'user': None if user is None else {
            'id': user._store.id,
            'group': user._store.group,
            'group_disp': user._store.group_disp(),
            'token': user._store.token,
            'profile': {
                field: (
                    getattr(user._store.profile, f'{field}_or_null') or ''
                ) for field in UserProfileStore.PROFILE_FOR_GROUP.get(user._store.group, [])
            },
            'terms_agreed': user._store.terms_agreed,
        },
        'feature': {
            'push': user is not None and user.check_play_game() is None,
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

    err = user.check_update_profile()
    if err is not None:
        return {'error': err[0], 'error_msg': err[1]}

    delta = time.time() - user._store.profile.timestamp_ms/1000
    if delta<3:
        return {'error': 'RATE_LIMIT', 'error_msg': f'提交太频繁，请等待 {2-delta:.1f} 秒'}

    required_fields = user._store.profile.PROFILE_FOR_GROUP.get(user._store.group, [])
    fields = {}
    profile = UserProfileStore()
    for field in required_fields:
        if field not in body.profile:
            return {'error': 'INVALID_PARAM', 'error_msg': f'缺少 {field} 信息'}
        setattr(profile, f'{field}_or_null', str(body.profile[field]))
        fields[field] = str(body.profile[field])

    chk = profile.check_profile(user._store.group)
    if chk is not None:
        return {'error': 'INVALID_PARAM', 'error_msg': chk}

    rep = await worker.perform_action(glitter.UpdateProfileReq(
        client=worker.process_name,
        uid=user._store.id,
        profile=fields,
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
        'list': [ann.describe_json() for ann in worker.game.announcements.list],
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

FALLBACK_CAT_COLOR = '#000000'

def reorder_by_cat(values: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for cat in ChallengeStore.CAT_COLORS.keys():
        if cat in values:
            out[cat] = None
    for k, v in values.items():
        out[k] = v
    return out

@wish_endpoint(bp, '/game')
async def get_game(_req: Request, worker: Worker, user: Optional[User]) -> Dict[str, Any]:
    if user is None:
        return {'error': 'NO_USER', 'error_msg': '未登录'}
    if worker.game is None:
        return {'error': 'NO_GAME', 'error_msg': '服务暂时不可用'}

    err = user.check_play_game()
    if err is not None:
        return {'error': err[0], 'error_msg': err[1]}

    policy = worker.game.policy.cur_policy
    active_board_key = 'score_pku' if user._store.group=='pku' else 'score_all'
    active_board_name = '北京大学' if user._store.group=='pku' else '总'
    active_board = worker.game.boards[active_board_key]
    assert isinstance(active_board, ScoreBoard)

    return {
        'challenge_list': None if not policy.can_view_problem else [{
            'id': ch._store.id,
            'title': ch._store.title,
            'category': ch._store.category,
            'category_color': ChallengeStore.CAT_COLORS.get(ch._store.category, FALLBACK_CAT_COLOR),

            'desc': ch.desc,
            'actions': ch._store.actions,
            'flags': [f.describe_json(user) for f in ch.flags],

            'tot_base_score': ch.tot_base_score,
            'tot_cur_score': ch.tot_cur_score,
            'passed_users_count': len(ch.passed_users),
            'status': ch.user_status(user),
        } for ch in worker.game.challenges.list if ch.cur_effective],

        'user_info': {
            'status_line': f'总分 {user.tot_score}，{active_board_name}排名 {active_board.uid_to_rank.get(user._store.id, "--")}',
            'tot_score_by_cat': [(k, v) for k, v in reorder_by_cat(user.tot_score_by_cat).items()] if user.tot_score_by_cat else None,
            'active_board_key': active_board_key,
        },

        'show_writeup': policy.can_submit_writeup,
        'last_announcement': worker.game.announcements.list[0].describe_json() if worker.game.announcements.list else None,
    }

@dataclass
class SubmitFlagParam:
    challenge_id: int
    flag: str

@wish_endpoint(bp, '/submit_flag')
@validate(json=SubmitFlagParam)
async def submit_flag(_req: Request, body: SubmitFlagParam, worker: Worker, user: Optional[User]) -> Dict[str, Any]:
    if user is None:
        return {'error': 'NO_USER', 'error_msg': '未登录'}
    if worker.game is None:
        return {'error': 'NO_GAME', 'error_msg': '服务暂时不可用'}

    err = user.check_play_game()
    if err is not None:
        return {'error': err[0], 'error_msg': err[1]}
    if not worker.game.policy.cur_policy.can_submit_flag:
        return {'error': 'POLICY_ERROR', 'error_msg': '现在不允许提交Flag'}

    err = ChallengeStore.check_submitted_flag(body.flag)
    if err is not None:
        return {'error': err[0], 'error_msg': err[1]}

    last_sub = user.last_submission
    if last_sub is not None:
        delta = time.time()-last_sub._store.timestamp_ms/1000
        if delta<10:
            return {'error': 'RATE_LIMIT', 'error_msg': f'提交太频繁，请等待 {10-delta:.1f} 秒'}

    rep = await worker.perform_action(glitter.SubmitFlagReq(
        client=worker.process_name,
        uid=user._store.id,
        challenge_id=body.challenge_id,
        flag=body.flag,
    ))
    if rep.error_msg is not None:
        return {'error': 'REDUCER_ERROR', 'error_msg': rep.error_msg}

    return {}

@wish_endpoint(bp, '/get_touched_users/<challenge_id:int>')
async def get_touched_users(_req: Request, challenge_id: int, worker: Worker, user: Optional[User]) -> Dict[str, Any]:
    if user is None:
        return {'error': 'NO_USER', 'error_msg': '未登录'}
    if worker.game is None:
        return {'error': 'NO_GAME', 'error_msg': '服务暂时不可用'}

    err = user.check_play_game()
    if err is not None:
        return {'error': err[0], 'error_msg': err[1]}

    ch = worker.game.challenges.chall_by_id.get(challenge_id, None)
    if ch is None:
        return {'error': 'NOT_FOUND', 'error_msg': '题目不存在'}

    users: Dict[User, List[Submission]] = {}
    users_sort_key: List[Tuple[Tuple[int, int], User]] = []
    for u in ch.touched_users:
        li = []
        tot_score = 0
        last_sub_ts = 0
        for f in ch.flags:
            sub = u.passed_flags.get(f, None)
            if sub is not None:
                li.append(sub)
                last_sub_ts = max(last_sub_ts, sub._store.timestamp_ms)
                tot_score += sub.gained_score()
        users[u] = li
        users_sort_key.append(((-tot_score, last_sub_ts), u))

    users_sort_key.sort(key=lambda x: x[0])

    return {
        'list': [{
            'nickname': u._store.profile.nickname_or_null or '',
            'group_disp': u._store.group_disp(),
            'flags': [int(sub._store.timestamp_ms/1000) for sub in users[u]],
        } for _sort_key, u in users_sort_key],
    }

@wish_endpoint(bp, '/board/<board_name:str>')
async def get_board(_req: Request, board_name: str, worker: Worker) -> Dict[str, Any]:
    if worker.game is None:
        return {'error': 'NO_GAME', 'error_msg': '服务暂时不可用'}

    b = worker.game.boards.get(board_name, None)
    if b is None:
        return {'error': 'NOT_FOUND', 'error_msg': '排行榜不存在'}

    return {
        **b.summarized,
        'type': b.board_type,
    }

@wish_endpoint(bp, '/submissions')
async def get_submissions(_req: Request, worker: Worker, user: Optional[User]) -> Dict[str, Any]:
    if user is None:
        return {'error': 'NO_USER', 'error_msg': '未登录'}
    if worker.game is None:
        return {'error': 'NO_GAME', 'error_msg': '服务暂时不可用'}

    err = user.check_play_game()
    if err is not None:
        return {'error': err[0], 'error_msg': err[1]}

    def get_overrides(sub: Submission) -> List[str]:
        ret: List[str] = []

        if sub.duplicate_submission:
            ret.append('重复提交')

        if sub._store.score_override_or_null is not None:
            ret.append(f'分数 = {sub._store.score_override_or_null}')
        elif sub._store.precentage_override_or_null is not None:
            ret.append(f'分数 * {sub._store.precentage_override_or_null}%')

        return ret

    return {
        'list': [{
            'idx': idx, # row key
            'challenge_title': sub.challenge._store.title if sub.challenge else None,
            'matched_flag': sub.matched_flag.name if sub.matched_flag else None,
            'gained_score': sub.gained_score(),
            'overrides': get_overrides(sub),
            'timestamp_s': int(sub._store.timestamp_ms/1000),
        } for idx, sub in enumerate(user.submissions[::-1])],
    }

file_ext_re = re.compile(r'^.*?((?:\.[a-z0-9]+)+)$')
def get_file_ext(filename: str) -> str:
    m = file_ext_re.match(filename.lower())
    return '.bin' if m is None else m.group(1)

@wish_endpoint(bp, '/writeup', methods=['POST', 'PUT'])
async def writeup(req: Request, worker: Worker, user: Optional[User]) -> Dict[str, Any]:
    if user is None:
        return {'error': 'NO_USER', 'error_msg': '未登录'}
    if worker.game is None:
        return {'error': 'NO_GAME', 'error_msg': '服务暂时不可用'}

    err = user.check_submit_writeup()
    if err is not None:
        return {'error': err[0], 'error_msg': err[1]}
    if not worker.game.policy.cur_policy.can_submit_writeup:
        return {'error': 'POLICY_ERROR', 'error_msg': '暂时不允许提交Writeup'}

    user_writeup_dir_path = secret.WRITEUP_PATH / str(user._store.id)
    user_writeup_metadata_path = user_writeup_dir_path / 'metadata.json'

    if req.method=='POST':
        metadata: Optional[Dict[str, Any]] = None
        if user_writeup_metadata_path.is_file():
            with user_writeup_metadata_path.open('r') as f:
                metadata = json.load(f)

        return {
            'writeup_required': user.writeup_required(),
            'submitted_metadata': None if metadata is None else {
                k: metadata[k]
                for k in ['filename', 'size', 'sha256', 'publish', 'rights']
            },
            'max_size_mb': secret.WRITEUP_MAX_SIZE_MB,
        }

    elif req.method=='PUT':
        if user_writeup_metadata_path.is_file():
            with user_writeup_metadata_path.open('r') as f:
                filename = json.load(f)['filename']
            assert '/' not in filename and '\\' not in filename

            old_file = user_writeup_dir_path/filename
            if old_file.is_file():
                delta = time.time() - old_file.stat().st_mtime
                if delta<60:
                    return {'error': 'RATE_LIMIT', 'error_msg': f'提交太频繁，请等待 {60-delta:.1f} 秒'}

        file: Optional[File] = req.files.get('file', None)
        publish = req.form.get('publish', None)
        rights = req.form.get('rights', None)

        if (
            publish is None or publish not in ['Always-Yes', 'Always-No', 'Maybe']
            or rights is None or rights not in ['CC0', 'CC-BY-NC', 'All-Rights-Reserved']
            or file is None
        ):
            return {'error': 'INVALID_ARGUMENT', 'error_msg': '参数错误'}

        if len(file.body)>secret.WRITEUP_MAX_SIZE_MB*1024*1024:
            return {'error': 'FILE_TOO_LARGE', 'error_msg': 'Writeup 文件太大'}

        timestamp_ms = int(time.time()*1000)
        filename = f'{user._store.id}_writeup_{timestamp_ms}{get_file_ext(file.name)}'
        assert '/' not in filename and '\\' not in filename

        user_writeup_dir_path.mkdir(parents=True, exist_ok=True)

        with (user_writeup_dir_path / filename).open('wb') as f:
            f.write(file.body) # type: ignore
        with (user_writeup_dir_path / filename).open('rb') as f:
            sha256 = hashlib.sha256(f.read()).hexdigest() # type: ignore

        metadata = {
            'publish': publish,
            'rights': rights,
            'timestamp_ms': timestamp_ms,
            'size': len(file.body),
            'filename': filename,
            'original_filename': file.name,
            'sha256': sha256,
        }

        with user_writeup_metadata_path.open('w') as f:
            json.dump(metadata, f, indent=2)

        return {}

    else:
        return {'error': 'HTTP_METHOD_ERROR', 'error_msg': '不支持的 HTTP 方法'}