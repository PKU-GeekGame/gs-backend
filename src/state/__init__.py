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

from .announcement import Announcement, Announcements
from .board import Board, ScoreBoard, FirstBloodBoard
from .flag import Flag
from .challenge import Challenge, Challenges
from .game_policy import GamePolicy
from .submission import Submission
from .trigger import Trigger
from .user import User, Users

from .game import Game
