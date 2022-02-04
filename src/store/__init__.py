from sqlalchemy import Column, Integer
from sqlalchemy.orm import declarative_base  # type: ignore

SqlBase = declarative_base()

class Table(SqlBase):  # type: ignore
    __abstract__ = True
    id = Column(Integer, primary_key=True)

from .AnnouncementStore import AnnouncementStore
from .ChallengeStore import ChallengeStore
from .GamePolicyStore import GamePolicyStore
from .LogStore import LogStore
from .SubmissionStore import SubmissionStore
from .TriggerStore import TriggerStore
from .UserProfileStore import UserProfileStore
from .UserStore import UserStore
