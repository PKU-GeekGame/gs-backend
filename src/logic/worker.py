from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from typing import Type, TypeVar, List, Optional

from ..state import *
from ..store import *
from .. import secret

T = TypeVar('T', bound=Table)

class Worker:
    def __init__(self, process_name: str):
        self.process_name: str = process_name
        self.Session = sessionmaker(create_engine(secret.DB_CONNECTOR, future=True), expire_on_commit=False, future=True)

        self.game: Game = Game(
            logger=self.logger,
            cur_tick=0,
            game_policy_stores=self.load_all_data(GamePolicyStore),
            trigger_stores=self.load_all_data(TriggerStore),
            challenge_stores=self.load_all_data(ChallengeStore),
            announcement_stores=self.load_all_data(AnnouncementStore),
            user_stores=self.load_all_data(UserStore),
        )

        self.game.cur_tick = self.register_from_reducer()
        self.game.on_tick_change()

        self.need_reloading_scoreboard = False
        self.game.on_scoreboard_reset()

        for submission in self.load_all_data(SubmissionStore):
            self.game.on_scoreboard_update(submission, in_batch=True)
        self.game.on_scoreboard_batch_update_done()

    def register_from_reducer(self) -> int: # returns current tick
        return 0 # todo

    def logger(self, level: str, module: str, message: str) -> None:
        with self.Session() as session:
            log = LogStore(level=level, process=self.process_name, module=module, message=message)
            session.add(log)
            session.commit()

    def load_all_data(self, cls: Type[T]) -> List[T]:
        with self.Session() as session:
            return session.execute(select(cls)).scalars().all() # type: ignore

    def load_one_data(self, cls: Type[Table], id: int) -> Optional[T]:
        with self.Session() as session:
            return session.execute(select(cls).where(cls.id==id)).scalar() # type: ignore