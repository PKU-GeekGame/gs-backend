from sqlalchemy import Column, Integer
from sqlalchemy.orm import declarative_base  # type: ignore

SqlBase = declarative_base()

class Table(SqlBase):  # type: ignore
    __abstract__ = True
    id = Column(Integer, primary_key=True)

from .announcement_store import AnnouncementStore
from .challenge_store import ChallengeStore
from .game_policy_store import GamePolicyStore
from .log_store import LogStore
from .submission_store import SubmissionStore
from .trigger_store import TriggerStore
from .user_profile_store import UserProfileStore
from .user_store import UserStore
