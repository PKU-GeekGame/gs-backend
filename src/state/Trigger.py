from __future__ import annotations
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from . import *
    from ..store import *

class Trigger:
    def __init__(self, game: Game, stores: List[TriggerStore]):
        self._game: Game = game
        self._stores: List[TriggerStore] = []

        self.on_store_reload(stores)

    def on_store_reload(self, stores: List[TriggerStore]):
        self._stores = stores
        self._game.need_reloading_scoreboard = True

    def get_tick_at_time(self, timestamp_s: float) -> int:
        tick = 0
        for store in self._stores:
            if store.timestamp_s<=timestamp_s:
                tick = store.tick
        return tick