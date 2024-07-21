from __future__ import annotations
from typing import TYPE_CHECKING, List, Dict

if TYPE_CHECKING:
    from ..logic.base import StateContainerBase
from . import WithGameLifecycle, Submission, Trigger, GamePolicy, Announcements, Challenges, Users, Board, ScoreBoard, FirstBloodBoard
from ..store import *

class Game(WithGameLifecycle):
    def __init__(self,
            worker: StateContainerBase,
            cur_tick: int,
            game_policy_stores: List[GamePolicyStore],
            trigger_stores: List[TriggerStore],
            challenge_stores: List[ChallengeStore],
            announcement_stores: List[AnnouncementStore],
            user_stores: List[UserStore],
            use_boards: bool,
    ):
        self.worker: StateContainerBase = worker
        self.log = self.worker.log

        self.cur_tick: int = cur_tick
        self.need_reloading_scoreboard: bool = True
        self.submissions: Dict[int, Submission] = {}

        self.trigger: Trigger = Trigger(self, trigger_stores)
        self.policy: GamePolicy = GamePolicy(self, game_policy_stores)
        self.announcements: Announcements = Announcements(self, announcement_stores)
        self.challenges: Challenges = Challenges(self, challenge_stores)
        self.users: Users = Users(self, user_stores)
        self.boards: Dict[str, Board] = {
            'score_pku': ScoreBoard('北京大学排名', None, self, UserStore.MAIN_BOARD_GROUPS, False, 100),
            'first_pku': FirstBloodBoard('北京大学一血榜', None, self, UserStore.MAIN_BOARD_GROUPS, False),
            'score_all': ScoreBoard('总排名', '只有用户组为 “北京大学” 的用户参与评奖', self, UserStore.TOT_BOARD_GROUPS, True, 150),
            'first_all': FirstBloodBoard('总一血榜', None, self, UserStore.TOT_BOARD_GROUPS, True),
        } if use_boards else {}

        self.n_corr_submission: int = 0

    def on_tick_change(self) -> None:
        self.policy.on_tick_change()
        self.challenges.on_tick_change()
        self.users.on_tick_change()
        for b in self.boards.values():
            b.on_tick_change()

    def on_scoreboard_reset(self) -> None:
        self.submissions = {}
        self.n_corr_submission = 0

        self.policy.on_scoreboard_reset()
        self.challenges.on_scoreboard_reset()
        self.users.on_scoreboard_reset()
        for b in self.boards.values():
            b.on_scoreboard_reset()

    def on_scoreboard_update(self, submission: Submission, in_batch: bool) -> None:
        if submission._store.id in self.submissions:
            self.log('error', 'game.on_scoreboard_update', f'dropping processed submission #{submission._store.id}')
            return

        if not in_batch:
            self.log('debug', 'game.on_scoreboard_update', f'received submission #{submission._store.id}')

        self.submissions[submission._store.id] = submission

        #self.policy.on_scoreboard_update(submission, in_batch) # optimized out because nothing to do
        self.challenges.on_scoreboard_update(submission, in_batch)
        self.users.on_scoreboard_update(submission, in_batch)
        for b in self.boards.values():
            b.on_scoreboard_update(submission, in_batch)

        if submission.matched_flag is not None:
            self.n_corr_submission += 1

    def on_scoreboard_batch_update_done(self) -> None:
        self.log('debug', 'game.on_scoreboard_batch_update_done', f'batch update received {len(self.submissions)} submissions')

        self.policy.on_scoreboard_batch_update_done()
        self.challenges.on_scoreboard_batch_update_done()
        self.users.on_scoreboard_batch_update_done()
        for b in self.boards.values():
            b.on_scoreboard_batch_update_done()

    def clear_boards_render_cache(self) -> None:
        for b in self.boards.values():
            b.clear_render_cache()