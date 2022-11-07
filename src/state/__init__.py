from __future__ import annotations
from abc import ABC

class WithGameLifecycle(ABC):
    def on_tick_change(self) -> None:
        pass

    def on_scoreboard_reset(self) -> None:
        pass

    def on_scoreboard_update(self, submission: Submission, in_batch: bool) -> None:
        pass

    def on_scoreboard_batch_update_done(self) -> None:
        pass

from .trigger_state import Trigger
from .board_state import Board, ScoreBoard, FirstBloodBoard
from .flag_state import Flag
from .challenge_state import Challenge, Challenges
from .game_policy_state import GamePolicy
from .submission_state import Submission
from .user_state import User, Users
from .announcement_state import Announcement, Announcements

from .game_state import Game