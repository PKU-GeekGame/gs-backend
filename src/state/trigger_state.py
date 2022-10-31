from __future__ import annotations
import time
from typing import TYPE_CHECKING, List, Tuple, Dict, Optional

if TYPE_CHECKING:
    from . import *
    from ..store import *

class Trigger:
    TS_INF_S = 90000000000 # a timestamp in the future. actually at 4821-12-27

    TRIGGER_BOARD_BEGIN = 1000
    TRIGGER_BOARD_END = 9000

    def __init__(self, game: Game, stores: List[TriggerStore]):
        self._game: Game = game
        self._stores: List[TriggerStore] = []
        self.trigger_by_tick: Dict[int, TriggerStore] = {}

        self.board_begin_ts: int = 0
        self.board_end_ts: int = 0

        self.on_store_reload(stores)

    def on_store_reload(self, stores: List[TriggerStore]) -> None:
        self._stores = sorted(stores, key=lambda s: s.timestamp_s)
        self.trigger_by_tick = {s.tick: s for s in self._stores}

        self._game.need_reloading_scoreboard = True

        if self.TRIGGER_BOARD_BEGIN in self.trigger_by_tick:
            self.board_begin_ts = self.trigger_by_tick[self.TRIGGER_BOARD_BEGIN].timestamp_s
        else:
            self._game.log('error', 'trigger.on_store_reload',
                'trigger_board_begin not found, estimating a time for it')
            self.board_begin_ts = self._stores[0].timestamp_s if len(self._stores)>0 else int(time.time())-600

        if self.TRIGGER_BOARD_END in self.trigger_by_tick:
            self.board_end_ts = self.trigger_by_tick[self.TRIGGER_BOARD_END].timestamp_s
        else:
            self._game.log('error', 'trigger.on_store_reload', 'trigger_board_end not found, estimating a time for it')
            self.board_end_ts = self._stores[-1].timestamp_s if len(self._stores)>0 else int(time.time())+600

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

    def describe_cur_tick(self) -> Tuple[str, Optional[int], Optional[str]]: # (cur_trigger_name, next_trigger_timestamp_s, next_trigger_name)
        cur_trigger = None
        next_trigger = None

        for i, store in enumerate(self._stores):
            if store.tick==self._game.cur_tick:
                cur_trigger = store
                next_trigger = self._stores[i+1] if i<len(self._stores)-1 else None

        return (
            cur_trigger.name if cur_trigger else '??',
            next_trigger.timestamp_s if next_trigger else None,
            next_trigger.name if next_trigger else None,
        )