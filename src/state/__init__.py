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

from .Announcement import Announcement, Announcements
from .Board import Board, ScoreBoard, FirstBloodBoard
from .Flag import Flag
from .Challenge import Challenge, Challenges
from .GamePolicy import GamePolicy
from .Submission import Submission
from .Trigger import Trigger
from .User import User, Users

from .Game import Game
