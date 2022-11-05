from __future__ import annotations
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, List, Tuple, Dict, Any

if TYPE_CHECKING:
    from . import *
    ScoreBoardItemType = Tuple[User, int]
from . import WithGameLifecycle
from .. import utils

def minmax(x: int, a: int, b: int) -> int:
    if x<a: return a
    elif x>b: return b
    return x

class Board(WithGameLifecycle, ABC):
    def __init__(self, board_type: str, name: str, desc: Optional[str], game: Game):
        self.board_type = board_type
        self.name = name
        self.desc = desc
        self._game = game
        self._rendered: Optional[Dict[str, Any]] = None

    @property
    def rendered(self) -> Dict[str, Any]:
        if self._rendered is None:
            with utils.log_slow(self._game.worker.log, 'board.render', f'render {self.board_type} board {self.name}'):
                self._rendered = self._render()
        return self._rendered

    def clear_render_cache(self) -> None:
        self._rendered = None

    @abstractmethod
    def _render(self) -> Dict[str, Any]:
        raise NotImplementedError()

class ScoreBoard(Board):
    MAX_DISPLAY_USERS = 100
    MAX_TOPSTAR_USERS = 10

    def __init__(self, name: str, desc: Optional[str], game: Game, group: Optional[List[str]], show_group: bool):
        super().__init__('score', name, desc, game)

        self.show_group: bool = show_group
        self.group: Optional[List[str]] = group
        self.board: List[ScoreBoardItemType] = []
        self.uid_to_rank: Dict[int, int] = {}

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

        b = [(u, u.tot_score) for u in self._game.users.list]
        self.board = sorted([x for x in b if is_valid(x)], key=sorter)
        self.uid_to_rank = {user._store.id: idx+1 for idx, (user, _score) in enumerate(self.board)}

    def _render(self) -> Dict[str, Any]:
        self._game.worker.log('debug', 'board.render', f'rendering score board {self.name}')

        return {
            'challenges': [{
                'key': ch._store.key,
                'title': ch._store.title,
                'category': ch._store.category,
                'flags': [f.name for f in ch.flags],
            } for ch in self._game.challenges.list if ch.cur_effective],

            'list': [{
                'rank': idx+1,
                'nickname': u._store.profile.nickname_or_null or '--',
                'group_disp': u._store.group_disp() if self.show_group else None,
                'badges': u._store.badges(),
                'score': score,
                'last_succ_submission_ts': int(u.last_succ_submission._store.timestamp_ms/1000) if u.last_succ_submission else None,
                'challenge_status': {
                    ch._store.key: ch.user_status(u)
                    for ch in self._game.challenges.list if ch.cur_effective
                },
                'flag_status': {
                    f'{f.challenge._store.key}_{f.idx0}': {
                        'timestamp_s': int(sub._store.timestamp_ms/1000),
                        'gained_score': sub.gained_score(),
                    }
                    for f, sub in u.passed_flags.items()
                },
            } for idx, (u, score) in enumerate(self.board[:self.MAX_DISPLAY_USERS])],

            'topstars': [{
                'nickname': u._store.profile.nickname_or_null or '--',
                'submissions': [{
                    'timestamp_ms': sub._store.timestamp_ms,
                    'gained_score': sub.gained_score(),
                } for sub in u.succ_submissions]
            } for u, _score in self.board[:self.MAX_TOPSTAR_USERS]],

            'time_range': [
                self._game.trigger.board_begin_ts,
                minmax(int(time.time())+1, self._game.trigger.board_begin_ts+1, self._game.trigger.board_end_ts),
            ],
        }

    def on_scoreboard_reset(self) -> None:
        self.board = []
        self.clear_render_cache()

    def on_scoreboard_update(self, submission: Submission, in_batch: bool) -> None:
        if not in_batch and submission.matched_flag is not None:
            if self.group is None or submission.user._store.group in self.group:
                self._update_board()
                self.clear_render_cache()

    def on_scoreboard_batch_update_done(self) -> None:
        self._update_board()
        self.clear_render_cache()

class FirstBloodBoard(Board):
    def __init__(self, name: str, desc: Optional[str], game: Game, group: Optional[List[str]], show_group: bool):
        super().__init__('firstblood', name, desc, game)

        self.show_group: bool = show_group
        self.group: Optional[List[str]] = group
        self.chall_board: Dict[Challenge, Submission] = {}
        self.flag_board: Dict[Flag, Submission] = {}

        self._rendered: Optional[Dict[str, Any]] = None

    @property
    def rendered(self) -> Dict[str, Any]:
        if self._rendered is None:
            self._rendered = self._render()
        return self._rendered

    def clear_render_cache(self) -> None:
        self._rendered = None

    def _render(self) -> Dict[str, Any]:
        self._game.worker.log('debug', 'board.render', f'rendering first blood board {self.name}')

        return {
            'list': [{
                'title': ch._store.title,
                'key': ch._store.key,

                'flags': [{
                    'flag_name': None,
                    'nickname': ch_sub.user._store.profile.nickname_or_null if ch_sub is not None else None,
                    'group_disp': ch_sub.user._store.group_disp() if (ch_sub is not None and self.show_group) else None,
                    'badges': ch_sub.user._store.badges() if ch_sub is not None else None,
                    'timestamp': int(ch_sub._store.timestamp_ms/1000) if ch_sub is not None else None,
                }] + ([] if len(ch.flags)<=1 else [{
                    'flag_name': f.name,
                    'nickname': f_sub.user._store.profile.nickname_or_null if f_sub is not None else None,
                    'group_disp': f_sub.user._store.group_disp() if (f_sub is not None and self.show_group) else None,
                    'badges': f_sub.user._store.badges() if f_sub is not None else None,
                    'timestamp': int(f_sub._store.timestamp_ms/1000) if f_sub is not None else None,
                } for f in ch.flags for f_sub in [self.flag_board.get(f, None)]]),

            } for ch in self._game.challenges.list if ch.cur_effective for ch_sub in [self.chall_board.get(ch, None)]],
        }

    def on_scoreboard_reset(self) -> None:
        self.chall_board = {}
        self.flag_board = {}
        self.clear_render_cache()

    def on_scoreboard_update(self, submission: Submission, in_batch: bool) -> None:
        if submission.matched_flag is not None:
            assert submission.challenge is not None, 'submission matched flag to no challenge'

            if self.group is None or submission.user._store.group in self.group:
                passed_all_flags = submission.challenge in submission.user.passed_challs

                if submission.matched_flag not in self.flag_board:
                    self.flag_board[submission.matched_flag] = submission

                    if not in_batch and not passed_all_flags:
                        self._game.worker.emit_local_message({
                            'type': 'push',
                            'payload': {
                                'type': 'flag_first_blood',
                                'board_name': self.name,
                                'nickname': submission.user._store.profile.nickname_or_null,
                                'challenge': submission.challenge._store.title,
                                'flag': submission.matched_flag.name,
                            },
                            'togroups': self.group,
                        })

                if submission.challenge not in self.chall_board and passed_all_flags:
                    self.chall_board[submission.challenge] = submission

                    if not in_batch:
                        self._game.worker.emit_local_message({
                            'type': 'push',
                            'payload': {
                                'type': 'challenge_first_blood',
                                'board_name': self.name,
                                'nickname': submission.user._store.profile.nickname_or_null,
                                'challenge': submission.challenge._store.title,
                            },
                            'togroups': self.group,
                        })

                self.clear_render_cache()