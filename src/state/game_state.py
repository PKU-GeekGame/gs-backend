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
            'score_pku': ScoreBoard('北京大学排名', None, self, ['pku'], False, 100),
            'score_thu': ScoreBoard('清华大学排名', None, self, ['thu'], False, 100),
            'score_other': ScoreBoard('其他选手排名', '其他选手不参与评奖，但符合要求的可申请领取成绩证明和纪念品', self, ['other'], False, 100),
            'first_pku': FirstBloodBoard('北京大学一血榜', None, self, ['pku'], False),
            'first_thu': FirstBloodBoard('清华大学一血榜', '题目一血与奖项无关，仅供参考', self, ['thu'], False),
            'first_other': FirstBloodBoard('其他选手一血榜', '题目一血与奖项无关，仅供参考', self, ['other'], False),
            'score_all': ScoreBoard('总排名', '总排名与校内奖项无关，仅供参考', self, UserStore.TOT_BOARD_GROUPS, True, 200),
            'first_all': FirstBloodBoard('总一血榜', None, self, UserStore.TOT_BOARD_GROUPS, True),
            'banned': ScoreBoard('封神榜', 'R.I.P.', self, ['banned'], True, 200),
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