from sqlalchemy import Column, Integer
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Table(Base):
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
