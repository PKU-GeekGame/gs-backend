from __future__ import annotations
from typing import TYPE_CHECKING, List

from . import WithGameLifecycle
# noinspection PyUnresolvedReferences
from ..store import GamePolicyStore

class GamePolicy(WithGameLifecycle):
    def __init__(self, game: Game, stores: List[GamePolicyStore]):
        self._game: Game = game
        self._stores: List[GamePolicyStore] = []

        self.cur_policy: GamePolicyStore = GamePolicyStore.fallback_policy()

        self.on_store_reload(stores)

    def on_store_reload(self, stores: List[GamePolicyStore]) -> None:
        self._stores = sorted(stores, key=lambda x: x.effective_after)
        self.on_tick_change()
        self._game.need_reloading_scoreboard = True

    def get_policy_at_tick(self, tick: int) -> GamePolicyStore:
        ret = GamePolicyStore.fallback_policy()
        for s in self._stores:
            if s.effective_after <= tick:
                ret = s
        return ret

    def get_policy_at_time(self, timestamp_s: int) -> GamePolicyStore:
        tick = self._game.trigger.get_tick_at_time(timestamp_s)[0]
        return self.get_policy_at_tick(tick)

    def on_tick_change(self) -> None:
        self.cur_policy = self.get_policy_at_tick(self._game.cur_tick)

if TYPE_CHECKING:
    from . import *
    from ..store import *