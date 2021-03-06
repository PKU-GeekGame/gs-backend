from __future__ import annotations
from typing import TYPE_CHECKING, List, Dict, Optional, Set, Union, Literal

if TYPE_CHECKING:
    from . import Game, Submission, User
    from ..store import *
from . import WithGameLifecycle, Flag
from .. import utils

class Challenges(WithGameLifecycle):
    def __init__(self, game: Game, stores: List[ChallengeStore]):
        self._game: Game = game
        self._stores: List[ChallengeStore] = []

        self.list: List[Challenge] = []
        self.chall_by_id: Dict[int, Challenge] = {}
        self.chall_by_key: Dict[str, Challenge] = {}

        self.on_store_reload(stores)

    def _after_chall_changed(self) -> None:
        self.list = sorted(self.list, key=lambda x: x._store.sorting_index)
        self.chall_by_id = {ch._store.id: ch for ch in self.list}
        self.chall_by_key = {ch._store.key: ch for ch in self.list}

    def on_store_reload(self, stores: List[ChallengeStore]) -> None:
        self._stores = stores
        self.list = [Challenge(self._game, store) for store in stores]
        self._after_chall_changed()
        self._game.need_reloading_scoreboard = True

    def on_store_update(self, id: int, new_store: Optional[ChallengeStore]) -> None:
        old_chall: Optional[Challenge] = ([x for x in self.list if x._store.id==id]+[None])[0]  # type: ignore
        other_challs = [x for x in self.list if x._store.id!=id]

        if new_store is None: # remove
            self.list = other_challs
            self._game.need_reloading_scoreboard = True
        elif old_chall is None: # add
            self.list = other_challs+[Challenge(self._game, new_store)]
            self._game.need_reloading_scoreboard = True
        else: # modify
            old_chall.on_store_reload(new_store)

        self._after_chall_changed()

    def on_tick_change(self) -> None:
        for ch in self.list:
            ch.on_tick_change()

    def on_scoreboard_reset(self) -> None:
        for ch in self.list:
            ch.on_scoreboard_reset()

    def on_scoreboard_update(self, submission: Submission, in_batch: bool) -> None:
        if submission.challenge is not None:
            submission.challenge.on_scoreboard_update(submission, in_batch)

class Challenge(WithGameLifecycle):
    def __init__(self, game: Game, store: ChallengeStore):
        self._game: Game = game
        self._store: ChallengeStore = store

        self.cur_effective: bool = False
        self.flags: List[Flag] = []
        self.desc: str = ''

        self.passed_users: Set[User] = set()
        self.touched_users: Set[User] = set()

        self.tot_base_score: int = 0
        self.tot_cur_score: int = 0

        self.on_store_reload(store)

    def on_store_reload(self, store: ChallengeStore) -> None:
        self._store = store
        self.desc = utils.render_template(self._store.desc_template)

        if store.flags!=[x._store for x in self.flags]:
            self.flags = [Flag(self._game, x, self, i) for i, x in enumerate(store.flags)]
            self._game.need_reloading_scoreboard = True

    def on_tick_change(self) -> None:
        self.cur_effective = self._game.cur_tick >= self._store.effective_after

        for flag in self.flags:
            flag.on_tick_change()

    def on_scoreboard_reset(self) -> None:
        self.passed_users = set()
        self.touched_users = set()

        for flag in self.flags:
            flag.on_scoreboard_reset()

        self._update_tot_score()

    def on_scoreboard_update(self, submission: Submission, in_batch: bool) -> None:
        if submission.challenge is not None and submission.challenge._store.id==self._store.id: # always true as delegated from Challenges
            all_passed = True
            for flag in self.flags:
                flag.on_scoreboard_update(submission, in_batch)

                if submission.user not in flag.passed_users:
                    all_passed = False

            if all_passed:
                self.passed_users.add(submission.user)

            if submission.matched_flag is not None:
                self._update_tot_score()
                self.touched_users.add(submission.user)

    def _update_tot_score(self) -> None:
        self.tot_base_score = 0
        self.tot_cur_score = 0

        for flag in self.flags:
            self.tot_base_score += flag.base_score
            self.tot_cur_score += flag.cur_score

    def user_status(self, user: User) -> Union[Literal['passed'], Literal['partial'], Literal['untouched']]:
        if user in self.passed_users:
            return 'passed'
        elif user in self.touched_users:
            return 'partial'
        else:
            return 'untouched'

    def __repr__(self) -> str:
        return f'[Ch#{self._store.id} {self._store.key}: {self._store.title}]'