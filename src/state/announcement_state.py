from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional

from .. import utils

class Announcements:
    def __init__(self, game: Game, stores: List[AnnouncementStore]):
        self._game: Game = game

        self.list: List[Announcement] = []

        self.on_store_reload(stores)

    def _sort_list(self) -> None:
        self.list = sorted(self.list, key=lambda x: x._store.id, reverse=True)

    def on_store_reload(self, stores: List[AnnouncementStore]) -> None:
        self.list = [Announcement(self._game, x) for x in stores]
        self._sort_list()

    def on_store_update(self, id: int, new_store: Optional[AnnouncementStore]) -> None:
        other_anns = [x for x in self.list if x._store.id!=id]

        if new_store is None:
            self.list = other_anns
        else:
            self.list = other_anns+[Announcement(self._game, new_store)]

        self._sort_list()

class Announcement:
    def __init__(self, game: Game, store: AnnouncementStore):
        self._game: Game = game
        self._store: AnnouncementStore = store

        self.title = store.title
        self.content = utils.render_template(store.content_template)
        self.timestamp_s = store.timestamp_s

    def __repr__(self) -> str:
        return repr(self._store)

if TYPE_CHECKING:
    from . import Game
    from ..store import *