from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from . import *
    from ..store import *
from . import WithGameLifecycle

class GamePolicy(WithGameLifecycle):
    def __init__(self, game: Game, stores: List[GamePolicyStore]):
        self._game: Game = game
        self._stores: List[GamePolicyStore] = []

        self.cur_policy: Optional[GamePolicyStore] = None

        self.on_store_reload(stores)

    def on_store_reload(self, stores: List[GamePolicyStore]):
        self._stores = sorted(stores, key=lambda x: x.effective_after)
        self.on_tick_change()
        self._game.need_reloading_scoreboard = True

    def get_policy_at_tick(self, tick: int) -> Optional[GamePolicyStore]:
        ret = None
        for s in self._stores:
            if s.effective_after <= tick:
                ret = s
        return ret

    def get_policy_at_time(self, timestamp_s: float) -> Optional[GamePolicyStore]:
        return self.get_policy_at_tick(self._game.trigger.get_tick_at_time(timestamp_s))

    def on_tick_change(self):
        self.cur_policy = self.get_policy_at_tick(self._game.cur_tick)

    def on_scoreboard_reset(self):
        pass

    def on_scoreboard_update(self, submission: Submission, in_batch: bool):
        pass