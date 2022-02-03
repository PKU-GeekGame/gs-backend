from __future__ import annotations
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from . import *
    from ..store import *
from .. import utils

class Announcements:
    def __init__(self, game: Game, stores: List[AnnouncementStore]):
        self._game: Game = game
        self._stores: List[AnnouncementStore] = []

        self.list: List[Announcement] = []

        self.on_store_reload(stores)

    def on_store_reload(self, stores: List[AnnouncementStore]) -> None:
        self._stores = sorted(stores, key=lambda x: x.timestamp_s, reverse=True)
        self.list = [Announcement(self._game, x) for x in self._stores]

class Announcement:
    def __init__(self, game: Game, store: AnnouncementStore):
        self._game: Game = game
        self._store: AnnouncementStore = store

        self.content = utils.render_template(self._store.content_template)
        self.time_str = utils.format_timestamp(self._store.timestamp_s)