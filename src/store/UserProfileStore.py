from sqlalchemy import Column, Integer, ForeignKey, BigInteger, String
from sqlalchemy.orm import relationship
import time

from . import Table

class UserProfileStore(Table):
    __tablename__ = 'user_profile'

    MAX_INFO_LEN = 128

    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    user = relationship('UserStore', lazy='select', foreign_keys=[user_id])
    timestamp_ms = Column(BigInteger, nullable=False, default=lambda: int(1000*time.time()))

    nickname_or_null = Column('nickname', String(MAX_INFO_LEN), nullable=True)
    qq_or_null = Column('qq', String(MAX_INFO_LEN), nullable=True)
    tel_or_null = Column('tel', String(MAX_INFO_LEN), nullable=True)
    email_or_null = Column('email', String(MAX_INFO_LEN), nullable=True)
    gender_or_null = Column('gender', String(MAX_INFO_LEN), nullable=True)
    comment_or_null = Column('comment', String(MAX_INFO_LEN), nullable=True)

    def __repr__(self):
        return f'<nick={self.nickname_or_null!r} qq={self.qq_or_null!r} email={self.email_or_null!r}>'