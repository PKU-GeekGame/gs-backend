from sqlalchemy import Column, Integer
from sqlalchemy.orm import declarative_base, Mapped

class _SqlBase:
    __allow_unmapped__ = True

SqlBase = declarative_base(cls=_SqlBase)

class Table(SqlBase):
    __abstract__ = True
    id: Mapped[int] = Column(Integer, primary_key=True)

from .announcement_store import AnnouncementStore
from .challenge_store import ChallengeStore, FlagType
from .game_policy_store import GamePolicyStore
from .log_store import LogStore
from .submission_store import SubmissionStore
from .trigger_store import TriggerStore
from .user_store import UserStore
from .user_profile_store import UserProfileStore
from .feedback_store import FeedbackStore
