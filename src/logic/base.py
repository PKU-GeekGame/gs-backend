from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from zmq.asyncio import Context
# noinspection PyUnresolvedReferences
from abc import ABC, abstractmethod
import asyncio
from typing import Type, TypeVar, List, Optional, Dict, Callable, Any, Tuple

from . import glitter
from ..state import *
from ..store import *
from .. import utils
from .. import secret

T = TypeVar('T', bound=Table)
CbMethod = Callable[[Any, Any], Any]

def make_callback_decorator() -> Tuple[Callable[[Any], Callable[[CbMethod], CbMethod]], Dict[Any, CbMethod]]:
    listeners: Dict[Any, CbMethod] = {}

    def decorator(event_name: Any) -> Callable[[CbMethod], CbMethod]:
        def wrapper(fn: CbMethod) -> CbMethod:
            if fn is not listeners.get(event_name, fn):
                raise RuntimeError('event listener already registered:', event_name)

            listeners[event_name] = fn
            return fn

        return wrapper

    return decorator, listeners

on_event, event_listeners = make_callback_decorator()

class StateContainerBase(ABC):
    RECOVER_THROTTLE_S = .5
    MAX_KEEPING_MESSAGES = 20

    def __init__(self, process_name: str, receiving_messages: bool = False):
        self.process_name: str = process_name
        self.SqlSession = sessionmaker(create_engine(secret.DB_CONNECTOR, future=True), expire_on_commit=False, future=True)

        self.log('debug', 'base.__init__', f'{self.process_name} started')

        self.glitter_ctx: Context = Context() # type: ignore

        # initialized later in self.init_game
        self._game: Game = None # type: ignore

        self.game_dirty: bool = True

        self.local_messages: Dict[int, Tuple[Optional[List[str]], Dict[str, Any]]] = {}
        self.next_message_id: int = 1
        self.message_cond: asyncio.Condition = None  # type: ignore
        self.listening_local_messages: bool = receiving_messages

    @property
    def game(self) -> Optional[Game]:
        if self.game_dirty:
            return None
        return self._game

    async def init_game(self, tick: int) -> None:
        while True:
            try:
                self._game = Game(
                    worker=self,
                    cur_tick=tick,
                    game_policy_stores=self.load_all_data(GamePolicyStore),
                    trigger_stores=self.load_all_data(TriggerStore),
                    challenge_stores=self.load_all_data(ChallengeStore),
                    announcement_stores=self.load_all_data(AnnouncementStore),
                    user_stores=self.load_all_data(UserStore),
                )
                self._game.on_tick_change()
                self.reload_scoreboard_if_needed()
            except Exception as e:
                self.log('error', 'base.init_game', f'exception during initialization, will try again: {utils.get_traceback(e)}')
                await asyncio.sleep(self.RECOVER_THROTTLE_S)
            else:
                break

    async def _before_run(self) -> None:
        self.message_cond = asyncio.Condition()

    @abstractmethod
    async def _mainloop(self) -> None:
        raise NotImplementedError()

    async def run_forever(self) -> None:
        await self._before_run()

        # _before_run should call init_game to initialize `self.game` field
        assert self._game is not None, 'game state not initialized in _before_run'
        assert not self.game_dirty, 'game state should be set to not dirty after _before_run'

        await self._mainloop()

    @on_event(glitter.EventType.SYNC)
    def on_sync(self, event: glitter.Event) -> None:
        if self._game.cur_tick!=event.data:
            self.log('error', 'base.on_sync', f'tick is inconsistent: ours {self._game.cur_tick}, synced {event.data}')
            self._game.cur_tick = event.data
            self._game.on_tick_change()

    @on_event(glitter.EventType.RELOAD_GAME_POLICY)
    def on_reload_game_policy(self, _event: glitter.Event) -> None:
        self._game.policy.on_store_reload(self.load_all_data(GamePolicyStore))

    @on_event(glitter.EventType.RELOAD_TRIGGER)
    def on_reload_trigger(self, _event: glitter.Event) -> None:
        self._game.trigger.on_store_reload(self.load_all_data(TriggerStore))

    @on_event(glitter.EventType.RELOAD_SUBMISSION)
    def on_reload_submission(self, _event: glitter.Event) -> None:
        self._game.need_reloading_scoreboard = True

    @on_event(glitter.EventType.UPDATE_ANNOUNCEMENT)
    def on_update_announcement(self, event: glitter.Event) -> None:
        self._game.announcements.on_store_update(event.data, self.load_one_data(AnnouncementStore, event.data))

    @on_event(glitter.EventType.UPDATE_CHALLENGE)
    def on_update_challenge(self, event: glitter.Event) -> None:
        self._game.challenges.on_store_update(event.data, self.load_one_data(ChallengeStore, event.data))

    @on_event(glitter.EventType.UPDATE_USER)
    def on_update_user(self, event: glitter.Event) -> None:
        self._game.users.on_store_update(event.data, self.load_one_data(UserStore, event.data))

    @on_event(glitter.EventType.NEW_SUBMISSION)
    def on_new_submission(self, event: glitter.Event) -> None:
        sub_store = self.load_one_data(SubmissionStore, event.data)
        assert sub_store is not None, 'submission not found'
        sub = Submission(self._game, sub_store)
        self._game.on_scoreboard_update(sub, in_batch=False)

    @on_event(glitter.EventType.TICK_UPDATE)
    def on_tick_update(self, event: glitter.Event) -> None:
        old_tick = self._game.cur_tick
        if old_tick!=event.data:
            self._game.cur_tick = event.data
            self._game.on_tick_change()

            if event.data in self._game.trigger.trigger_by_tick:
                self.emit_local_message({
                    'type': 'tick_update',
                    'new_tick_name': self._game.trigger.trigger_by_tick[event.data].name,
                })

    def reload_scoreboard_if_needed(self) -> None:
        if not self._game.need_reloading_scoreboard:
            return

        self._game.need_reloading_scoreboard = False
        self._game.on_scoreboard_reset()

        for sub_store in self.load_all_data(SubmissionStore):
            submission = Submission(self._game, sub_store)
            self._game.on_scoreboard_update(submission, in_batch=True)
        self._game.on_scoreboard_batch_update_done()

    def log(self, level: str, module: str, message: str) -> None:
        print(f'{self.process_name} [{level}] {module}: {message}')

        if level!='debug':
            with self.SqlSession() as session:
                log = LogStore(level=level, process=self.process_name, module=module, message=message)
                session.add(log)
                session.commit()

    def load_all_data(self, cls: Type[T]) -> List[T]:
        with self.SqlSession() as session:
            return session.execute(select(cls)).scalars().all() # type: ignore

    def load_one_data(self, cls: Type[T], id: int) -> Optional[T]:
        with self.SqlSession() as session:
            return session.execute(select(cls).where(cls.id==id)).scalar() # type: ignore

    async def process_event(self, event: glitter.Event) -> None:
        def default(_self: Any, ev: glitter.Event) -> None:
            self.log('warning', 'base.process_event', f'unknown event: {ev.type!r}')

        listener = event_listeners.get(event.type, default)

        try:
            listener(self, event)
            self.reload_scoreboard_if_needed()
        except Exception as e:
            self.log('critical', 'base.process_event', f'exception during event listener, will recover: {e!r}')
            self.game_dirty = True
            await self.init_game(self._game.cur_tick)
            self.game_dirty = False
            await asyncio.sleep(self.RECOVER_THROTTLE_S)

    def emit_local_message(self, msg: Dict[str, Any], togroup: Optional[List[str]] = None) -> None:
        if not self.listening_local_messages:
            return

        self.log('debug', 'base.emit_local_message', f'emit message {msg.get("type", None)}')

        self.local_messages[self.next_message_id] = (togroup, msg)

        deleted_message = self.next_message_id-self.MAX_KEEPING_MESSAGES
        if deleted_message in self.local_messages:
            del self.local_messages[deleted_message]

        self.next_message_id += 1

        async def notify_waiters():
            async with self.message_cond:
                self.message_cond.notify_all()

        asyncio.get_event_loop().create_task(notify_waiters())