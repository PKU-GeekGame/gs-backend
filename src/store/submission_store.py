from sqlalchemy import Column, Integer, String, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from . import UserStore
from . import Table

class SubmissionStore(Table):
    __tablename__ = 'submission'

    SUBMIT_COOLDOWN_S = 10
    MAX_FLAG_LEN = 128

    user_id: int = Column(Integer, ForeignKey('user.id'), nullable=False)
    user_: 'UserStore' = relationship('UserStore', lazy='select', foreign_keys=[user_id])
    challenge_key: str = Column(String(32), nullable=False)
    flag: str = Column(String(MAX_FLAG_LEN), nullable=False)
    timestamp_ms: int = Column(BigInteger, nullable=False, default=lambda: int(1000*time.time()))

    score_override_or_null = Column(Integer, nullable=True)
    precentage_override_or_null = Column(Integer, nullable=True)

    def tweak_score(self, flag_score: int) -> int:
        if self.score_override_or_null is not None:
            return self.score_override_or_null

        if self.precentage_override_or_null is not None:
            return int(flag_score * self.precentage_override_or_null / 100)

        return flag_score