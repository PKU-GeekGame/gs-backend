from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Dict, Set, Tuple

if TYPE_CHECKING:
    from . import Game, Submission, Flag, Challenge
    from ..store import *
from . import WithGameLifecycle

class Users(WithGameLifecycle):
    def __init__(self, game: Game, stores: List[UserStore]):
        self._game: Game = game
        self._stores: List[UserStore] = []

        self.list: List[User] = []
        self.user_by_id: Dict[int, User] = {}
        self.user_by_login_key: Dict[str, User] = {}
        self.user_by_auth_token: Dict[str, User] = {}

        self.on_store_reload(stores)

    def _update_aux_dicts(self) -> None:
        self.user_by_id = {u._store.id: u for u in self.list}
        self.user_by_login_key = {u._store.login_key: u for u in self.list}
        self.user_by_auth_token = {u._store.auth_token: u for u in self.list if u._store.auth_token is not None}

    def on_store_reload(self, stores: List[UserStore]) -> None:
        self._stores = stores
        self.list = [User(self._game, x) for x in self._stores]
        self._update_aux_dicts()
        self._game.need_reloading_scoreboard = True

    def on_store_update(self, id: int, new_store: Optional[UserStore]) -> None:
        old_user: Optional[User] = ([x for x in self.list if x._store.id==id]+[None])[0]  # type: ignore
        other_users = [x for x in self.list if x._store.id!=id]

        if new_store is None: # remove
            self.list = other_users
            self._game.need_reloading_scoreboard = True
        elif old_user is None:  # add
            self.list = other_users+[User(self._game, new_store)]
            # no need to reload scoreboard, because newly added user does not have any submissions yet
        else: # modify
            old_user.on_store_reload(new_store)

        self._update_aux_dicts()

    def on_scoreboard_reset(self) -> None:
        for user in self.list:
            user.on_scoreboard_reset()

    def on_scoreboard_update(self, submission: Submission, in_batch: bool) -> None:
        submission.user.on_scoreboard_update(submission, in_batch)

class User(WithGameLifecycle):
    def __init__(self, game: Game, store: UserStore):
        self._game: Game = game
        self._store: UserStore = store

        self.passed_flags: Set[Flag] = set()
        self.passed_challs: Set[Challenge] = set()
        self.succ_submissions: List[Submission] = []
        self.submissions: List[Submission] = []
        self.tot_score: int = 0
        self.tot_score_by_cat: Dict[str, int] = {}

        self.on_store_reload(self._store)

    def on_store_reload(self, store: UserStore) -> None:
        if self._store.group!=store.group:
            self._game.need_reloading_scoreboard = True

        self._store = store

    def on_scoreboard_reset(self) -> None:
        self.passed_flags = set()
        self.passed_challs = set()
        self.succ_submissions = []
        self.submissions = []
        self._update_tot_score()

    def on_scoreboard_update(self, submission: Submission, in_batch: bool) -> None:
        if submission._store.user_id==self._store.id: # always true as delegated from Users
            self.submissions.append(submission)

            if submission.matched_flag is not None:
                ch = submission.matched_flag.challenge

                self.passed_flags.add(submission.matched_flag)
                if self in ch.passed_users:
                    self.passed_challs.add(ch)

                self.succ_submissions.append(submission)

        if submission.matched_flag is not None and not in_batch:
            self._update_tot_score()

    def on_scoreboard_batch_update_done(self) -> None:
        self._update_tot_score()

    def _update_tot_score(self) -> None:
        self.tot_score = 0
        self.tot_score_by_cat = {}

        for f in self.passed_flags:
            cat = f.challenge._store.category
            self.tot_score += f.cur_score
            self.tot_score_by_cat.setdefault(cat, 0)
            self.tot_score_by_cat[cat] += f.cur_score

    @property
    def last_succ_submission(self) -> Optional[Submission]:
        return self.succ_submissions[-1] if len(self.succ_submissions)>0 else None

    @property
    def last_submission(self) -> Optional[Submission]:
        return self.submissions[-1] if len(self.submissions)>0 else None

    def get_tot_score(self) -> int:
        tot = 0
        for f in self.passed_flags:
            tot += f.cur_score
        return tot

    def check_login(self) -> Optional[str]:
        if not self._store.enabled:
            return '账号不允许登录'
        return None

    def check_update_profile(self) -> Optional[str]:
        if self.check_login() is not None:
            return self.check_login()
        if not self._store.terms_agreed:
            return '请先阅读比赛须知'
        if self._store.group=='banned':
            return '此用户组被禁止参赛'
        return None

    def check_play_game(self) -> Optional[str]:
        if self.check_update_profile() is not None:
            return self.check_update_profile()
        if self._store.profile.check_profile(self._store.group) is not None:
            return self._store.profile.check_profile(self._store.group)
        return None

    def __repr__(self) -> str:
        return repr(self._store)