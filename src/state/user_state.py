from __future__ import annotations
import hashlib
import json
from typing import TYPE_CHECKING, List, Optional, Dict, Tuple

if TYPE_CHECKING:
    from . import Game, Submission, Flag, Challenge
    from ..store import *
from . import WithGameLifecycle
from .. import secret
from ..state import ScoreBoard
from ..store import UserStore

# if secret.SCORE_OFFSET_PATH:
#     with open(secret.SCORE_OFFSET_PATH) as f:
#         SCORE_OFFSET = {int(k): v for k, v in json.load(f).items()}
# else:
#     SCORE_OFFSET = {}

class Users(WithGameLifecycle):
    #max_score_offset = max(SCORE_OFFSET.values(), default=0)

    def __init__(self, game: Game, stores: List[UserStore]):
        self._game: Game = game
        self._stores: List[UserStore] = []
        #self.max_score = 0

        self.list: List[User] = []
        self.user_by_id: Dict[int, User] = {}
        self.user_by_login_key: Dict[str, User] = {}
        self.user_by_auth_token: Dict[str, User] = {}
        self.user_by_token: Dict[str, User] = {}

        self.on_store_reload(stores)

    def _update_aux_dicts(self) -> None:
        self.user_by_id = {u._store.id: u for u in self.list}
        self.user_by_login_key = {u._store.login_key: u for u in self.list}
        self.user_by_auth_token = {u._store.auth_token: u for u in self.list if u._store.auth_token is not None}
        self.user_by_token = {u._store.token: u for u in self.list if u._store.token is not None}

    def on_store_reload(self, stores: List[UserStore]) -> None:
        self._stores = stores
        self.list = [User(self._game, x) for x in self._stores]
        self._update_aux_dicts()
        self._game.need_reloading_scoreboard = True

    def on_store_update(self, id: int, new_store: Optional[UserStore]) -> bool:
        reload_frontend = False

        # noinspection PyTypeChecker
        old_user: Optional[User] = ([x for x in self.list if x._store.id==id]+[None])[0]
        other_users = [x for x in self.list if x._store.id!=id]

        if new_store is None: # remove
            self.list = other_users
            self._game.need_reloading_scoreboard = True
        elif old_user is None:  # add
            self.list = other_users+[User(self._game, new_store)]
            # no need to reload scoreboard, because newly added user does not have any submissions yet
        else: # modify
            reload_frontend = old_user.on_store_reload(new_store)

        self._update_aux_dicts()

        if old_user is not None and old_user.tot_score>0:  # maybe on the board but profile changed
            self._game.clear_boards_render_cache()

        return reload_frontend

    def on_scoreboard_reset(self) -> None:
        for user in self.list:
            user.on_scoreboard_reset()

    def on_scoreboard_update(self, submission: Submission, in_batch: bool) -> None:
        submission.user.on_scoreboard_update(submission, in_batch)
        #if not in_batch:
        #    self.update_max_score()

    def on_scoreboard_batch_update_done(self) -> None:
        for user in self.list:
            user.on_scoreboard_batch_update_done()
        #self.update_max_score()

    #def update_max_score(self) -> None:
    #    self.max_score = max((u.tot_score for u in self.list if u._store.group in UserStore.TOT_BOARD_GROUPS), default=0)

class ScoreHistory:
    def __init__(self) -> None:
        self.last_ts = 0
        self.last_score = 0
        self.diff: List[Tuple[int, int]] = [] # (ts_delta, score_delta)

    def append(self, ts: int, score: int) -> None:
        score_diff = score-self.last_score
        if score_diff==0:
            return

        ts_diff = ts-self.last_ts

        if self.diff and ts_diff==0: # same ts, modify prev diff
            prev_ts_diff, prev_score_diff = self.diff[-1]
            self.diff[-1] = (prev_ts_diff, prev_score_diff+score_diff)
        else: # append a new diff
            self.diff.append((ts_diff, score_diff))

        self.last_ts = ts
        self.last_score = score

class User(WithGameLifecycle):
    WRITEUP_REQUIRED_RANKS = {
        'admin_s': 50, 'pentest_s': 50, 'dfir_s': 50,
        'admin_f': 25, 'pentest_f': 25, 'dfir_f': 25,
    }

    def __init__(self, game: Game, store: UserStore):
        self._game: Game = game
        self._store: UserStore = store

        self.passed_flags: Dict[Flag, Submission] = {}
        self.passed_challs: Dict[Challenge, Submission] = {}
        self.succ_submissions: List[Submission] = []
        self.submissions: List[Submission] = []
        self.tot_score: int = 0
        #self.score_offset: int = 0
        self.tot_score_by_cat: Dict[str, int] = {}

        self._score_history: Optional[ScoreHistory] = None

        self.on_store_reload(self._store)

    def on_store_reload(self, store: UserStore) -> bool:
        reload_frontend = False
        if self._store.group!=store.group:
            self._game.need_reloading_scoreboard = True
            reload_frontend = True

        self._store = store
        #self.score_offset = SCORE_OFFSET.get(self._store.id, 0)
        return reload_frontend

    def on_scoreboard_reset(self) -> None:
        self.passed_flags = {}
        self.passed_challs = {}
        self.succ_submissions = []
        self.submissions = []

        self._score_history = None # delay initialize to first use

        self._update_tot_score(None)

    def on_scoreboard_update(self, submission: Submission, in_batch: bool) -> None:
        assert submission._store.user_id==self._store.id # always true as delegated from Users

        self.submissions.append(submission)

        if submission.matched_flag is not None:
            ch = submission.matched_flag.challenge

            self.passed_flags[submission.matched_flag] = submission
            if self in ch.passed_users: # passed all flags in that challenge?
                self.passed_challs[ch] = submission

            self.succ_submissions.append(submission)

            if not in_batch:
                # update tot score of all passed users because their score might have changed
                for u in submission.matched_flag.passed_users:
                    u._update_tot_score(submission)


    def on_scoreboard_batch_update_done(self) -> None:
        self._update_tot_score(None)

    def _update_tot_score(self, score_updating_sub: Optional[Submission]) -> None:
        self.tot_score = 0
        self.tot_score_by_cat = {}

        for f, sub in self.passed_flags.items():
            cat = f.challenge._store.category
            score = sub.gained_score()

            self.tot_score += score

            old = self.tot_score_by_cat.get(cat, 0)
            self.tot_score_by_cat[cat] = old + score

        if score_updating_sub is not None and self._score_history is not None:
            self._score_history.append(score_updating_sub._store.timestamp_ms//1000, self.tot_score)

    def _recalc_score_history(self) -> None:
        events = []
        for f, sub in self.passed_flags.items():
            pass_sub_id = sub._store.id
            tweak = sub._store.tweak_score

            prev_score = 0
            _passed = False
            for since_id, score in f.score_history:
                if pass_sub_id<=since_id:
                    if not _passed:
                        _passed = True
                        events.append((pass_sub_id, prev_score))

                    delta = tweak(score)-prev_score
                    events.append((since_id, delta))

                prev_score = tweak(score)

            if not _passed:
                events.append((pass_sub_id, prev_score))

        events.sort(key=lambda x: x[0])

        self._score_history = ScoreHistory()
        tot_score = 0
        for sid, score_delta in events:
            time_s = self._game.submissions[sid]._store.timestamp_ms//1000
            tot_score += score_delta

            self._score_history.append(time_s, tot_score)

    @property
    def last_succ_submission(self) -> Optional[Submission]:
        return self.succ_submissions[-1] if len(self.succ_submissions)>0 else None

    @property
    def last_submission(self) -> Optional[Submission]:
        return self.submissions[-1] if len(self.submissions)>0 else None

    # @property
    # def normalized_tot_score(self) -> float:
    #     return (
    #         50 * self.tot_score / max(1e-10, self._game.users.max_score) +
    #         50 * self.score_offset / max(1e-10, self._game.users.max_score_offset)
    #     )

    @property
    def score_history_diff(self) -> List[Tuple[int, int]]:
        if self._score_history is None:
            self._recalc_score_history()
            assert self._score_history is not None

        return self._score_history.diff

    def check_login(self) -> Optional[Tuple[str, str]]:
        if not self._store.enabled:
            return 'USER_DISABLED', '账号不允许登录'
        return None

    def check_update_profile(self) -> Optional[Tuple[str, str]]:
        if self.check_login() is not None:
            return self.check_login()
        if not self._store.terms_agreed:
            return 'SHOULD_AGREE_TERMS', '请阅读参赛须知'
        if self._store.group=='banned':
            return 'USER_BANNED', '此用户组被禁止参赛'
        return None

    def check_play_game(self) -> Optional[Tuple[str, str]]:
        if self.check_update_profile() is not None:
            return self.check_update_profile()
        if self._store.profile.check_profile(self._store) is not None:
            return 'SHOULD_UPDATE_PROFILE', '请完善个人资料'
        return None

    def check_submit_writeup(self) -> Optional[Tuple[str, str]]:
        if self.check_play_game() is not None:
            return self.check_play_game()
        if len(self.passed_flags)==0:
            return 'NO_PASSED_FLAGS', '此账号没有通过任何题目，无法提交 Writeup'
        return None

    def writeup_required(self) -> bool:
        grp = self._store.group
        required_rank = self.WRITEUP_REQUIRED_RANKS.get(grp, None)
        if required_rank is None:
            return False

        board = self._game.boards[f'score_{self._store.group}']
        assert isinstance(board, ScoreBoard)

        rank = board.uid_to_rank.get(self._store.id, required_rank+1)
        return rank <= required_rank

    def get_partition(self, ch: Challenge, n_part: int) -> int: # for partitioned dynamic flag
        h = hashlib.sha256(f'{self._store.id}-{ch._store.key}'.encode()).hexdigest()
        return int(h, 16) % n_part

    def get_partitions(self, ch: Challenge, n_parts: List[int]) -> List[int]: # for wordlist dynamic flag
        tot_parts = 1
        for n in n_parts:
            assert isinstance(n, int) and n>0, 'each value in n_parts must be positive integers'
            tot_parts *= n

        part = self.get_partition(ch, tot_parts)
        ret = []
        for n in n_parts:
            ret.append(part % n)
            part //= n
        return ret

    def admin_badges(self) -> List[str]:
        return [
            #f'U#{self._store.id}',
            f'remark:U#{self._store.id} {self._store.login_key}',
        ]

    def __repr__(self) -> str:
        return repr(self._store)