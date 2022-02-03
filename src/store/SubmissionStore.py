from sqlalchemy import Column, Integer, String, ForeignKey, BigInteger
import time

from . import Table

class SubmissionStore(Table):
    __tablename__ = 'submission'

    MAX_FLAG_LEN = 128

    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    challenge_key = Column(String(32), nullable=False)
    flag = Column(String(MAX_FLAG_LEN), nullable=False)
    timestamp_ms = Column(BigInteger, nullable=False, default=lambda: int(1000*time.time()))

    score_override_or_null = Column(Integer, nullable=True)
    precentage_override_or_null = Column(Integer, nullable=True)