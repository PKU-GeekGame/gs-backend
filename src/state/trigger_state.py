from __future__ import annotations
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from . import *
    from ..store import *

class Trigger:
    TS_INF_S = 90000000000 # a timestamp in the future. actually at 4821-12-27

    def __init__(self, game: Game, stores: List[TriggerStore]):
        self._game: Game = game
        self._stores: List[TriggerStore] = []

        self.on_store_reload(stores)

    def on_store_reload(self, stores: List[TriggerStore]) -> None:
        self._stores = sorted(stores, key=lambda s: s.timestamp_s)
        self._game.need_reloading_scoreboard = True

    def get_tick_at_time(self, timestamp_s: int) -> Tuple[int, int]: # (current tick, timestamp when it expires)
        assert timestamp_s<self.TS_INF_S, 'you are in the future'

        if not self._stores:
            return 0, self.TS_INF_S

        idx = 0
        for i, store in enumerate(self._stores):
            if store.timestamp_s<=timestamp_s:
                idx = i

        expires = self.TS_INF_S
        if idx<len(self._stores)-1:
            expires = self._stores[idx+1].timestamp_s

        assert self._stores[idx].timestamp_s<expires # always true because timestamp is unique and sorted
        return self._stores[idx].tick, expires