from __future__ import annotations
from functools import lru_cache
from typing import TYPE_CHECKING, List, Optional, Dict, Any

from .. import utils
from . import User

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
            if len(other_anns)==len(self.list): # created announcement
                self._game.worker.emit_local_message({
                    'type': 'push',
                    'payload': {
                        'type': 'new_announcement',
                        'title': new_store.title,
                    },
                    'togroups': None,
                })
            self.list = other_anns+[Announcement(self._game, new_store)]

        self._sort_list()

class Announcement:
    def __init__(self, game: Game, store: AnnouncementStore):
        self._game: Game = game
        self._store: AnnouncementStore = store

        self.title = store.title
        self.timestamp_s = store.timestamp_s

    def __repr__(self) -> str:
        return repr(self._store)

    @lru_cache(16)
    def _render_template(self, tick: int, group: Optional[str]) -> str:
        try:
            return utils.render_template(self._store.content_template, {'group': group, 'tick': tick})
        except Exception as e:
            self._game.worker.log('error', 'announcement.render_template', f'template render failed: {self._store.id} ({self._store.title}): {utils.get_traceback(e)}')
            return '<i>（模板渲染失败）</i>'

    def describe_json(self, user: Optional[User]) -> Dict[str, Any]:
        return {
            'id': self._store.id,
            'title': self.title,
            'timestamp_s': self.timestamp_s,
            'content': self._render_template(self._game.cur_tick, None if user is None else user._store.group),
        }

if TYPE_CHECKING:
    from . import Game
    from ..store import *