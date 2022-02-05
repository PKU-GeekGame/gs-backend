from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from zmq.asyncio import Context
from abc import ABC, abstractmethod
from typing import Type, TypeVar, List, Optional, Dict, Callable, Any, Tuple

from . import glitter
from ..state import *
from ..store import *
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
    def __init__(self, process_name: str):
        self.process_name: str = process_name
        self.SqlSession = sessionmaker(create_engine(secret.DB_CONNECTOR, future=True), expire_on_commit=False, future=True)

        self.glitter_ctx: Context = Context() # type: ignore

        # self.game is initialized later in self.init_game
        self.game: Game = None # type: ignore

    def init_game(self) -> None:
        self.game = Game(
            logger=self.log,
            cur_tick=0,
            game_policy_stores=self.load_all_data(GamePolicyStore),
            trigger_stores=self.load_all_data(TriggerStore),
            challenge_stores=self.load_all_data(ChallengeStore),
            announcement_stores=self.load_all_data(AnnouncementStore),
            user_stores=self.load_all_data(UserStore),
        )
        self.game.on_tick_change()
        self.reload_scoreboard_if_needed()

    @abstractmethod
    async def _before_run(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def _mainloop(self) -> None:
        raise NotImplementedError()

    async def run_forever(self) -> None:
        await self._before_run()

        # _before_run should call init_game to initialize `self.game` field
        assert self.game is not None

        await self._mainloop()

    @on_event(glitter.EventType.SYNC)
    def on_sync(self, event: glitter.Event) -> None:
        pass

    @on_event(glitter.EventType.RELOAD_GAME_POLICY)
    def on_reload_game_policy(self, _event: glitter.Event) -> None:
        self.game.policy.on_store_reload(self.load_all_data(GamePolicyStore))

    @on_event(glitter.EventType.RELOAD_TRIGGER)
    def on_reload_trigger(self, _event: glitter.Event) -> None:
        self.game.trigger.on_store_reload(self.load_all_data(TriggerStore))

    @on_event(glitter.EventType.RELOAD_SUBMISSION)
    def on_reload_submission(self, _event: glitter.Event) -> None:
        self.game.need_reloading_scoreboard = True
        self.reload_scoreboard_if_needed()

    @on_event(glitter.EventType.UPDATE_ANNOUNCEMENT)
    def on_update_announcement(self, event: glitter.Event) -> None:
        self.game.announcements.on_store_update(event.data, self.load_one_data(AnnouncementStore, event.data))

    @on_event(glitter.EventType.UPDATE_CHALLENGE)
    def on_update_challenge(self, event: glitter.Event) -> None:
        self.game.challenges.on_store_update(event.data, self.load_one_data(ChallengeStore, event.data))

    @on_event(glitter.EventType.UPDATE_USER)
    def on_update_user(self, event: glitter.Event) -> None:
        self.game.users.on_store_update(event.data, self.load_one_data(UserStore, event.data))

    @on_event(glitter.EventType.NEW_SUBMISSION)
    def on_new_submission(self, event: glitter.Event) -> None:
        sub_store = self.load_one_data(SubmissionStore, event.data)
        assert sub_store is not None
        sub = Submission(self.game, sub_store)
        self.game.on_scoreboard_update(sub, in_batch=False)

    @on_event(glitter.EventType.TICK_UPDATE)
    def on_tick_update(self, event: glitter.Event) -> None:
        self.game.cur_tick = event.data
        self.game.on_tick_change()

    def reload_scoreboard_if_needed(self) -> None:
        if not self.game.need_reloading_scoreboard:
            return

        self.game.need_reloading_scoreboard = False
        self.game.on_scoreboard_reset()

        for sub_store in self.load_all_data(SubmissionStore):
            submission = Submission(self.game, sub_store)
            self.game.on_scoreboard_update(submission, in_batch=True)
        self.game.on_scoreboard_batch_update_done()

    def log(self, level: str, module: str, message: str) -> None:
        print(f'{self.process_name} [{level}] {module}: {message}')

        # with self.Session() as session:
        #     log = LogStore(level=level, process=self.process_name, module=module, message=message)
        #     session.add(log)
        #     session.commit()

    def load_all_data(self, cls: Type[T]) -> List[T]:
        with self.SqlSession() as session:
            return session.execute(select(cls)).scalars().all() # type: ignore

    def load_one_data(self, cls: Type[T], id: int) -> Optional[T]:
        with self.SqlSession() as session:
            return session.execute(select(cls).where(cls.id==id)).scalar() # type: ignore

    def process_event(self, event: glitter.Event) -> None:
        def default(_self: Any, e: glitter.Event) -> None:
            self.log('warning', 'base.process_event', f'unknown event: {e.type!r}')

        listener = event_listeners.get(event.type, default)
        listener(self, event)

        self.reload_scoreboard_if_needed()