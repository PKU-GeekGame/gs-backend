from abc import ABC

class WithGameLifecycle(ABC):
    def on_tick_change(self):
        pass

    def on_scoreboard_reset(self):
        pass

    def on_scoreboard_update(self, submission, in_batch: bool):
        pass

    def on_scoreboard_batch_update_done(self):
        pass

from .Announcement import Announcement, Announcements
from .Board import Board, ScoreBoard, FirstBloodBoard
from .Challenge import Challenge, Challenges
from .Flag import Flag
from .GamePolicy import GamePolicy
from .Submission import Submission
from .Trigger import Trigger
from .User import User, Users

from .Game import Game
