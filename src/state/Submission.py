from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from . import *
    from ..store import *

class Submission:
    def __init__(self, game: Game, store: SubmissionStore):
        self._game: Game = game
        self._store: SubmissionStore = store

        # foreign key constraint on SubmissionStore ensured user always exist
        self.user: User = self._game.users.user_by_id.get(self._store.user_id)

        # challenge be None if it is deleted later
        self.challenge: Optional[Challenge] = self._game.challenges.chall_by_key.get(self._store.challenge_key, None)

        self.matched_flag: Optional[Flag] = self._find_matched_flag()

    def _find_matched_flag(self) -> Optional[Flag]:
        if self.challenge is None:
            return None

        for flag in self.challenge.flags:
            if flag.validate_flag(self.user, self._store.flag):
                return flag

        return None

    def gained_score(self) -> int:
        # note that flag score is constantly changing

        if self._store.score_override_or_null is not None:
            return self._store.score_override_or_null

        if self.matched_flag is None:
            return 0

        score = self.matched_flag.cur_score

        if self._store.precentage_override_or_null is not None:
            score = int(score*self._store.precentage_override_or_null/100)

        return score