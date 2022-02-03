from __future__ import annotations
from typing import List, Dict, Callable

from . import *
from ..store import *

class Game(WithGameLifecycle):
    def __init__(self,
            logger: Callable[[str, str, str], None],
            cur_tick: int,
            game_policy_stores: List[GamePolicyStore],
            trigger_stores: List[TriggerStore],
            challenge_stores: List[ChallengeStore],
            announcement_stores: List[AnnouncementStore],
            user_stores: List[UserStore],
    ):
        self.log: Callable[[str, str, str], None] = logger # level, module, message
        self.cur_tick: int = cur_tick
        self.need_reloading_scoreboard: bool = False
        self.submissions: List[Submission] = []

        self.trigger: Trigger = Trigger(self, trigger_stores)
        self.policy: GamePolicy = GamePolicy(self, game_policy_stores)
        self.announcements: Announcements = Announcements(self, announcement_stores)
        self.challenges: Challenges = Challenges(self, challenge_stores)
        self.users: Users = Users(self, user_stores)
        self.boards: Dict[str, Board] = {
            'score_all': ScoreBoard(self, ['staff', 'pku', 'other']),
            'score_pku': ScoreBoard(self, ['pku']),
            'first_all': FirstBloodBoard(self, ['staff', 'pku', 'other']),
            'first_pku': FirstBloodBoard(self, ['pku']),
        }

    def on_tick_change(self):
        self.policy.on_tick_change()
        self.challenges.on_tick_change()
        self.users.on_tick_change()
        for b in self.boards.values():
            b.on_tick_change()

    def on_scoreboard_reset(self):
        self.submissions = []

        self.policy.on_scoreboard_reset()
        self.challenges.on_scoreboard_reset()
        self.users.on_scoreboard_reset()
        for b in self.boards.values():
            b.on_scoreboard_reset()

    def on_scoreboard_update(self, submission: Submission, in_batch: bool):
        self.submissions.append(submission)

        self.policy.on_scoreboard_update(submission, in_batch)
        self.challenges.on_scoreboard_update(submission, in_batch)
        self.users.on_scoreboard_update(submission, in_batch)
        for b in self.boards.values():
            b.on_scoreboard_update(submission, in_batch)

    def on_scoreboard_batch_update_done(self):
        self.policy.on_scoreboard_batch_update_done()
        self.challenges.on_scoreboard_batch_update_done()
        self.users.on_scoreboard_batch_update_done()
        for b in self.boards.values():
            b.on_scoreboard_batch_update_done()