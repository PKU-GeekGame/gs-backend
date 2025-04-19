from sqlalchemy import Column, Integer, String, ForeignKey, BigInteger, Text, Boolean
from sqlalchemy.orm import relationship
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from . import UserStore
from . import Table

class FeedbackStore(Table):
    __tablename__ = 'feedback'

    SUBMIT_COOLDOWN_S = 3600
    MAX_CONTENT_LEN = 1200

    user_id: int = Column(Integer, ForeignKey('user.id'), nullable=False)
    user_: 'UserStore' = relationship('UserStore', lazy='select', foreign_keys=[user_id])
    timestamp_ms = Column(BigInteger, nullable=False, default=lambda: int(1000*time.time()))
    challenge_key: str = Column(String(32), nullable=False)
    content = Column(Text, nullable=False)
    checked = Column(Boolean, nullable=False, default=False)