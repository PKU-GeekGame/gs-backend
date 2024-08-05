from sanic import Blueprint, Request
from sanic.request import File
from sanic_ext import validate
from dataclasses import dataclass
import time
import json
import re
import hashlib
from typing import Optional, Dict, Any, List, Tuple

from .. import store_anticheat_log
from ..wish import wish_endpoint
from ...state import User, ScoreBoard, Submission
from ...logic import Worker, glitter
from ...store import UserProfileStore, UserStore, ChallengeStore, SubmissionStore, FeedbackStore
from ... import utils
from ... import secret

bp = Blueprint('wish', url_prefix='/wish')

TEMPLATE_LIST = [
    ('faq', '选手常见问题', 0),
    ('credits', '工作人员', 9000),
]

@wish_endpoint(bp, '/game_info')
async def game_info(_req: Request, worker: Worker, user: Optional[User]) -> Dict[str, Any]:
    if worker.game is None:
        return {'error': 'NO_GAME', 'error_msg': '服务暂时不可用'}

    cur_tick = worker.game.cur_tick

    return {
        'user': None if user is None else {
            'id': user._store.id,
            'group': user._store.group,
            'group_disp': user._store.group_disp(),
            'badges': user._store.badges(),
            'token': user._store.token,
            'profile': {
                field: (
                    getattr(user._store.profile, f'{field}_or_null') or ''
                ) for field in UserProfileStore.PROFILE_FOR_GROUP.get(user._store.group, [])
            },
            'terms_agreed': user._store.terms_agreed,
        },
        'feature': {
            'push': secret.WS_PUSH_ENABLED and user is not None and user.check_play_game() is None,
            'game': user is not None or worker.game.policy.cur_policy.show_problems_to_guest,
            'submit_flag': worker.game.policy.cur_policy.can_submit_flag,
            'templates': [[key, title] for key, title, effective_after in TEMPLATE_LIST if cur_tick>=effective_after],
        },
        'diag_ts': int(time.time()),
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
    if delta<UserProfileStore.UPDATE_COOLDOWN_S:
        return {'error': 'RATE_LIMIT', 'error_msg': f'提交太频繁，请等待 {UserProfileStore.UPDATE_COOLDOWN_S-delta:.1f} 秒'}

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
async def announcements(_req: Request, worker: Worker, user: Optional[User]) -> Dict[str, Any]:
    if worker.game is None:
        return {'error': 'NO_GAME', 'error_msg': '服务暂时不可用'}

    return {
        'list': [ann.describe_json(user) for ann in worker.game.announcements.list],
    }

@wish_endpoint(bp, '/triggers')
async def triggers(_req: Request, worker: Worker) -> Dict[str, Any]:
    if worker.game is None:
        return {'error': 'NO_GAME', 'error_msg': '服务暂时不可用'}

    return {
        'list': [{
            'timestamp_s': trigger.timestamp_s,
            'name': trigger.name,
            'status': 'prs' if trigger.tick==worker.game.cur_tick else 'ftr' if trigger.tick>worker.game.cur_tick else 'pst',
        } for trigger in worker.game.trigger._stores]
    }

def reorder_by_cat(values: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for cat in ChallengeStore.CAT_COLORS.keys():
        if cat in values:
            out[cat] = None
    for k, v in values.items():
        out[k] = v
    return out

@wish_endpoint(bp, '/game')
async def get_game(req: Request, worker: Worker, user: Optional[User]) -> Dict[str, Any]:
    if worker.game is None:
        return {'error': 'NO_GAME', 'error_msg': '服务暂时不可用'}

    policy = worker.game.policy.cur_policy
    is_admin = user and secret.IS_ADMIN(user._store)

    user_info = None

    if user:
        err = user.check_play_game()
        if err is not None:
            return {'error': err[0], 'error_msg': err[1]}

        store_anticheat_log(req, ['open_game'])

        active_board_key = 'score_pku' if user._store.group in user._store.MAIN_BOARD_GROUPS else 'score_all'
        active_board_name = '北京大学' if user._store.group in user._store.MAIN_BOARD_GROUPS else '总'
        active_board = worker.game.boards[active_board_key]
        assert isinstance(active_board, ScoreBoard)

        user_info = {
            'tot_score': user.tot_score,
            'tot_score_by_cat': [(k, v) for k, v in reorder_by_cat(user.tot_score_by_cat).items()] if user.tot_score_by_cat else None,
            'board_key': active_board_key,
            'board_name': active_board_name,
            'board_rank': active_board.uid_to_rank.get(user._store.id, None),
        }
    else:
        if not policy.show_problems_to_guest:
            return {'error': 'NO_USER', 'error_msg': '未登录'}

    cur_trigger_name, next_trigger_timestamp_s, next_trigger_name = worker.game.trigger.describe_cur_tick()

    return {
        'challenge_list': None if (not policy.can_view_problem and not is_admin) else [{
            'key': ch._store.key,
            'title': ch._store.title + (f' [>={ch._store.effective_after}]' if not ch.cur_effective else ''),
            'category': ch._store.category,
            'category_color': ch._store.category_color(),

            'metadata': ch.describe_metadata(None),
            'flags': [f.describe_json(user) for f in ch.flags],
            'status': ch.user_status(user),

            'tot_base_score': ch.tot_base_score,
            'tot_cur_score': ch.tot_cur_score,
            'passed_users_count': len(ch.passed_users),
            'touched_users_count': len(ch.touched_users),
        } for ch in worker.game.challenges.list if ch.cur_effective or is_admin],

        'user_info': user_info,

        'trigger': {
            'current_name': cur_trigger_name,
            'next_timestamp_s': next_trigger_timestamp_s,
            'next_name': next_trigger_name,
        } if user else None,

        'show_writeup': policy.can_submit_writeup and user,
        'last_announcement': (
            worker.game.announcements.list[0].describe_json(user)
            if worker.game.announcements.list and user
            else None
        ),
    }

@wish_endpoint(bp, '/challenge/<challenge_key:str>')
async def get_challenge_details(req: Request, worker: Worker, user: Optional[User], challenge_key: str) -> Dict[str, Any]:
    if user is None:
        return {'error': 'NO_USER', 'error_msg': '未登录'}
    if worker.game is None:
        return {'error': 'NO_GAME', 'error_msg': '服务暂时不可用'}

    err = user.check_play_game()
    if err is not None:
        return {'error': err[0], 'error_msg': err[1]}

    is_admin = secret.IS_ADMIN(user._store)

    policy = worker.game.policy.cur_policy
    if not policy.can_view_problem and not is_admin:
        return {'error': 'NO_PERMISSION', 'error_msg': '现在不允许查看题目'}

    ch = worker.game.challenges.chall_by_key.get(challenge_key, None)
    if ch is None or (not ch.cur_effective and not is_admin):
        return {'error': 'NOT_FOUND', 'error_msg': '题目不存在'}

    store_anticheat_log(req, ['open_challenge', ch._store.key])

    return {
        'desc': ch.render_desc(user),
        'actions': ch._store.describe_actions(worker.game.cur_tick),
    }

@dataclass
class SubmitFlagParam:
    challenge_key: str
    flag: str

@wish_endpoint(bp, '/submit_flag')
@validate(json=SubmitFlagParam)
async def submit_flag(req: Request, body: SubmitFlagParam, worker: Worker, user: Optional[User]) -> Dict[str, Any]:
    if user is None:
        return {'error': 'NO_USER', 'error_msg': '未登录'}
    if worker.game is None:
        return {'error': 'NO_GAME', 'error_msg': '服务暂时不可用'}

    err = user.check_play_game()
    if err is not None:
        return {'error': err[0], 'error_msg': err[1]}
    if not worker.game.policy.cur_policy.can_submit_flag:
        return {'error': 'POLICY_ERROR', 'error_msg': '现在不允许提交Flag'}

    last_sub = user.last_submission
    if last_sub is not None:
        delta = time.time()-last_sub._store.timestamp_ms/1000
        if delta<SubmissionStore.SUBMIT_COOLDOWN_S:
            return {'error': 'RATE_LIMIT', 'error_msg': f'提交太频繁，请等待 {SubmissionStore.SUBMIT_COOLDOWN_S-delta:.1f} 秒'}

    ch = worker.game.challenges.chall_by_key.get(body.challenge_key, None)
    if ch is None or not ch.cur_effective:
        return {'error': 'NOT_FOUND', 'error_msg': '题目不存在'}

    err = ChallengeStore.check_flag_format(body.flag)
    if err is not None:
        store_anticheat_log(req, ['submit_flag', ch._store.key, body.flag, err])
        return {'error': err[0], 'error_msg': err[1]}

    rep = await worker.perform_action(glitter.SubmitFlagReq(
        client=worker.process_name,
        uid=user._store.id,
        challenge_key=body.challenge_key,
        flag=body.flag,
    ))

    store_anticheat_log(req, ['submit_flag', ch._store.key, body.flag, rep.error_msg])

    if rep.error_msg is not None:
        return {'error': 'REDUCER_ERROR', 'error_msg': rep.error_msg}

    return {}

@wish_endpoint(bp, '/get_touched_users/<challenge_key:str>')
async def get_touched_users(_req: Request, challenge_key: str, worker: Worker, user: Optional[User]) -> Dict[str, Any]:
    if user is None:
        return {'error': 'NO_USER', 'error_msg': '未登录'}
    if worker.game is None:
        return {'error': 'NO_GAME', 'error_msg': '服务暂时不可用'}

    err = user.check_play_game()
    if err is not None:
        return {'error': err[0], 'error_msg': err[1]}

    ch = worker.game.challenges.chall_by_key.get(challenge_key, None)
    if ch is None or not ch.cur_effective:
        return {'error': 'NOT_FOUND', 'error_msg': '题目不存在'}

    is_admin = secret.IS_ADMIN(user._store)

    users: Dict[User, List[Optional[Submission]]] = {}
    users_sort_key: List[Tuple[Tuple[int, int], User]] = []
    for u in ch.touched_users:
        li: List[Optional[Submission]] = []
        tot_score = 0
        last_sub_ts = 0
        for f in ch.flags:
            sub = u.passed_flags.get(f, None)
            if sub is not None:
                li.append(sub)
                last_sub_ts = max(last_sub_ts, sub._store.timestamp_ms)
                tot_score += sub.gained_score()
            else:
                li.append(None)
        users[u] = li
        users_sort_key.append(((-tot_score, last_sub_ts), u))

    users_sort_key.sort(key=lambda x: x[0])

    return {
        'list': [{
            'uid': u._store.id,
            'tot_score': u.tot_score,
            'nickname': u._store.profile.nickname_or_null or '',
            'group_disp': u._store.group_disp(),
            'badges': u._store.badges() + (u.admin_badges() if is_admin else []),
            'flags': [None if sub is None else int(sub._store.timestamp_ms/1000) for sub in users[u]],
        } for _sort_key, u in users_sort_key],
    }

@wish_endpoint(bp, '/board/<board_name:str>')
async def get_board(_req: Request, board_name: str, worker: Worker, user: Optional[User]) -> Dict[str, Any]:
    if worker.game is None:
        return {'error': 'NO_GAME', 'error_msg': '服务暂时不可用'}

    b = worker.game.boards.get(board_name, None)
    if b is None:
        return {'error': 'NOT_FOUND', 'error_msg': '排行榜不存在'}

    is_admin = user is not None and secret.IS_ADMIN(user._store)

    return {
        **b.get_rendered(is_admin),
        'type': b.board_type,
        'desc': b.desc,
    }

@wish_endpoint(bp, '/my_submissions')
async def get_my_submissions(_req: Request, worker: Worker, user: Optional[User]) -> Dict[str, Any]:
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
            'category': sub.challenge._store.category if sub.challenge else None,
            'category_color': sub.challenge._store.category_color() if sub.challenge else None,
            'matched_flag': sub.matched_flag.name if sub.matched_flag else None,
            'gained_score': sub.gained_score(),
            'overrides': get_overrides(sub),
            'timestamp_s': int(sub._store.timestamp_ms/1000),
        } for idx, sub in enumerate(user.submissions[::-1])],

        'topstars': [{
            'uid': user._store.id,
            'nickname': user._store.profile.nickname_or_null or '--',
            'history': user.score_history_diff,
        }],

        'time_range': [
            worker.game.trigger.board_begin_ts,
            worker.game.trigger.board_end_ts,
        ],
    }

@wish_endpoint(bp, '/submissions/<uid:int>')
async def get_others_submissions(_req: Request, uid: int, worker: Worker) -> Dict[str, Any]:
    if worker.game is None:
        return {'error': 'NO_GAME', 'error_msg': '服务暂时不可用'}

    user = worker.game.users.user_by_id.get(uid, None)
    if user is None or not user.succ_submissions:
        return {'error': 'NO_USER', 'error_msg': '用户不存在或未答出任何题目'}

    return {
        'list': [{
            'idx': idx, # row key
            'challenge_title': sub.challenge._store.title if sub.challenge else None,
            'category': sub.challenge._store.category if sub.challenge else None,
            'category_color': sub.challenge._store.category_color() if sub.challenge else None,
            'matched_flag': sub.matched_flag.name if sub.matched_flag else None,
            'gained_score': sub.gained_score(),
            'timestamp_s': int(sub._store.timestamp_ms/1000),
        } for idx, sub in enumerate(user.succ_submissions[::-1])],

        'topstars': [{
            'uid': user._store.id,
            'nickname': user._store.profile.nickname_or_null or '--',
            'history': user.score_history_diff,
        }],

        'time_range': [
            worker.game.trigger.board_begin_ts,
            worker.game.trigger.board_end_ts,
        ],
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
        return {'error': 'POLICY_ERROR', 'error_msg': '现在不允许提交Writeup'}

    user_writeup_path = user._store.writeup_path
    user_writeup_metadata_path = user._store.writeup_metadata_path

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

            old_file = user_writeup_path/filename
            if old_file.is_file():
                delta = time.time() - old_file.stat().st_mtime
                if delta<UserStore.WRITEUP_COOLDOWN_S:
                    return {'error': 'RATE_LIMIT', 'error_msg': f'提交太频繁，请等待 {UserStore.WRITEUP_COOLDOWN_S-delta:.1f} 秒'}

        if req.files is None or req.form is None:
            return {'error': 'INVALID_ARGUMENT', 'error_msg': '参数错误'}

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

        user_writeup_path.mkdir(parents=True, exist_ok=True)

        with (user_writeup_path / filename).open('wb') as f:
            f.write(file.body)
        with (user_writeup_path / filename).open('rb') as f:
            sha256 = hashlib.sha256(f.read()).hexdigest()

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

        await worker.push_message((
            f'[WRITEUP] U#{user._store.id} {user._store.login_key}\n'
            f' nick: {user._store.profile.nickname_or_null}\n'
            f' grp: {user._store.group} {user.tot_score}pt ({"" if user.writeup_required() else "NOT "}required)\n'
            f' filename: {file.name}\n'
            f' size: {utils.format_size(len(file.body))}'
        ), f'writeup:{user._store.id}')

        return {}

    else:
        return {'error': 'HTTP_METHOD_ERROR', 'error_msg': '不支持的 HTTP 方法'}

@dataclass
class SubmitFeedbackParam:
    challenge_key: str
    feedback: str

@wish_endpoint(bp, '/submit_feedback')
@validate(json=SubmitFeedbackParam)
async def submit_feedback(req: Request, body: SubmitFeedbackParam, worker: Worker, user: Optional[User]) -> Dict[str, Any]:
    if user is None:
        return {'error': 'NO_USER', 'error_msg': '未登录'}
    if worker.game is None:
        return {'error': 'NO_GAME', 'error_msg': '服务暂时不可用'}

    err = user.check_play_game()
    if err is not None:
        return {'error': err[0], 'error_msg': err[1]}
    if not worker.game.policy.cur_policy.can_submit_flag:
        return {'error': 'POLICY_ERROR', 'error_msg': '现在不允许提交反馈'}

    last_feedback_ms = user._store.last_feedback_ms
    if last_feedback_ms:
        delta = time.time()-last_feedback_ms/1000
        if delta<FeedbackStore.SUBMIT_COOLDOWN_S:
            return {'error': 'RATE_LIMIT', 'error_msg': f'提交太频繁，请等待 {FeedbackStore.SUBMIT_COOLDOWN_S-delta:.0f} 秒'}

    ch = worker.game.challenges.chall_by_key.get(body.challenge_key, None)
    if ch is None or not ch.cur_effective:
        return {'error': 'NOT_FOUND', 'error_msg': '题目不存在'}

    if len(body.feedback)>FeedbackStore.MAX_CONTENT_LEN:
        return {'error': 'CONTENT_LEN', 'error_msg': '反馈长度超过限制'}

    rep = await worker.perform_action(glitter.SubmitFeedbackReq(
        client=worker.process_name,
        uid=user._store.id,
        challenge_key=body.challenge_key,
        feedback=body.feedback,
    ))

    store_anticheat_log(req, ['submit_feedback', ch._store.key, body.feedback, rep.error_msg])

    if rep.error_msg is not None:
        return {'error': 'REDUCER_ERROR', 'error_msg': rep.error_msg}

    feedback_overview = (body.feedback[:200]+'…') if len(body.feedback)>200 else body.feedback
    feedback_overview = feedback_overview.replace('\r', '').replace('\n', ' ')
    await worker.push_message((
        f'[FEEDBACK] U#{user._store.id} {user._store.login_key}\n'
        f' nick: {user._store.profile.nickname_or_null}\n'
        f' grp: {user._store.group} {user.tot_score}pt\n'
        f' chal: ({ch._store.category}) {ch._store.key}\n\n'
        f'{feedback_overview}'
    ), f'feedback:{user._store.id}')

    return {}