from __future__ import annotations
from typing import TYPE_CHECKING, Optional

class Submission:
    def __init__(self, game: Game, store: SubmissionStore):
        self._game: Game = game
        self._store: SubmissionStore = store

        # foreign key constraint on SubmissionStore ensured user always exist
        self.user: User = self._game.users.user_by_id[self._store.user_id]

        # challenge be None if it is deleted later
        self.challenge: Optional[Challenge] = self._game.challenges.chall_by_key.get(self._store.challenge_key, None)

        self.duplicate_submission: bool = False # CORRECTLY answering a flag for the second time
        self.matched_flag: Optional[Flag] = self._find_matched_flag()

    def _find_matched_flag(self) -> Optional[Flag]:
        if self.challenge is None:
            return None

        for flag in self.challenge.flags:
            if flag.validate_flag(self.user, self._store.flag):
                if self.user in flag.passed_users:
                    self.duplicate_submission = True
                    return None
                else:
                    return flag

        return None

    def gained_score(self) -> int:
        if self.matched_flag is None:
            return 0
        else:
            return self._store.tweak_score(self.matched_flag.cur_score)

    def __repr__(self) -> str:
        return f'[Sub#{self._store.id} U#{self.user._store.id} Ch={self._store.challenge_key!r} Flag={self.matched_flag!r}]'

if TYPE_CHECKING:
    from . import Game, Challenge, Flag, User
    from ..store import *