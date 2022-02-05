from __future__ import annotations
from typing import TYPE_CHECKING, Optional, List, Tuple, Dict, Any
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from . import *
    ScoreBoardItemType = Tuple[User, int]
from . import WithGameLifecycle

class Board(WithGameLifecycle, ABC):
    @property
    @abstractmethod
    def summarized(self) -> object:
        raise NotImplementedError()

class ScoreBoard(Board):

    def __init__(self, game: Game, group: Optional[List[str]]):
        self._game = game

        self.group: Optional[List[str]] = group
        self.board: List[ScoreBoardItemType] = []

        self._summarized: object = self._summarize()

    @property
    def summarized(self) -> object:
        return self._summarized

    def _update_board(self) -> None:
        def is_valid(x: ScoreBoardItemType) -> bool:
            user, score = x
            return (
                ((user._store.group in self.group) if self.group is not None else True)
                and score>0
            )

        def sorter(x: ScoreBoardItemType) -> Tuple[Any, ...]:
            user, score = x
            return (
                -score,
                -1 if user.last_succ_submission is None else user.last_succ_submission._store.id,
            )

        b = [(u, u.get_tot_score()) for u in self._game.users.list]
        self.board = sorted([x for x in b if is_valid(x)], key=sorter)

    def _summarize(self) -> object:
        pass # todo

    def on_scoreboard_reset(self) -> None:
        self.board = []
        self._summarized = self._summarize()

    def on_scoreboard_update(self, submission: Submission, in_batch: bool) -> None:
        if not in_batch and submission.matched_flag is not None:
            self._update_board()
            self._summarized = self._summarize()

    def on_scoreboard_batch_update_done(self) -> None:
        self._update_board()
        self._summarized = self._summarize()

class FirstBloodBoard(Board):
    def __init__(self, game: Game, group: Optional[List[str]]):
        self._game = game

        self.group: Optional[List[str]] = group
        self.chall_board: Dict[Challenge, Optional[User]] = {}
        self.flag_board: Dict[Flag, Optional[User]] = {}

        self._summarized: object = self._summarize()

    @property
    def summarized(self) -> object:
        return self._summarized

    def _summarize(self) -> object:
        pass # todo

    def on_scoreboard_reset(self) -> None:
        self.chall_board = {ch: None for ch in self._game.challenges.list}
        self.flag_board = {f: None for ch in self._game.challenges.list for f in ch.flags}
        self._summarized = self._summarize()

    def on_scoreboard_update(self, submission: Submission, in_batch: bool) -> None:
        if submission.matched_flag is not None:
            assert submission.challenge is not None, 'submission matched flag to no challenge'
            if self.group is None or submission.user._store.group in self.group:
                self.chall_board.setdefault(submission.challenge, submission.user)
                self.flag_board.setdefault(submission.matched_flag, submission.user)
                self._summarized = self._summarize()