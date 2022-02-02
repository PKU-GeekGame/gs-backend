from sqlalchemy import Column, Integer, String, ForeignKey, BigInteger
import time

from . import Table

class SubmissionStore(Table):
    __tablename__ = 'submission'

    MAX_FLAG_LEN = 128

    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    challenge_id = Column(Integer, ForeignKey('challenge.id'), nullable=False)
    flag = Column(String(MAX_FLAG_LEN), nullable=False)
    timestamp_ms = Column(BigInteger, nullable=False, default=lambda: int(1000*time.time()))