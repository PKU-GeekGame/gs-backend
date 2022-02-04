from sqlalchemy import Column, Integer, ForeignKey, BigInteger, String
from sqlalchemy.orm import relationship
import time
import re
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from . import UserStore
from . import Table

class UserProfileStore(Table):
    __tablename__ = 'user_profile'

    MAX_INFO_LEN = 128

    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    user_ = relationship('UserStore', lazy='select', foreign_keys=[user_id])
    timestamp_ms = Column(BigInteger, nullable=False, default=lambda: int(1000*time.time()))

    nickname_or_null = Column('nickname', String(MAX_INFO_LEN), nullable=True)
    VAL_NICKNAME = re.compile(r'^.{1,20}$')

    qq_or_null = Column('qq', String(MAX_INFO_LEN), nullable=True)
    VAL_QQ = re.compile(r'^.{5,50}$')

    tel_or_null = Column('tel', String(MAX_INFO_LEN), nullable=True)
    VAL_TEL = re.compile(r'^.{5,20}$')

    email_or_null = Column('email', String(MAX_INFO_LEN), nullable=True)
    VAL_EMAIL = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')

    gender_or_null = Column('gender', String(MAX_INFO_LEN), nullable=True)
    VAL_GENDER = re.compile(r'^(female|male|other)$')

    comment_or_null = Column('comment', String(MAX_INFO_LEN), nullable=True)
    VAL_COMMENT = re.compile(r'^.{0,100}$')

    PROFILE_FOR_GROUP = {
        'staff': ['nickname', 'gender', 'tel', 'qq'],
        'pku': ['nickname', 'gender', 'tel', 'qq'],
        'other': ['nickname', 'qq'],
        'banned': ['nickname', 'qq'],
    }

    def check_profile(self, group: str) -> Optional[str]:
        for field in self.PROFILE_FOR_GROUP.get(group, []):
            if getattr(self, f'{field}_or_null') is None:
                return f'个人信息不完整（{field}）'

        if self.nickname_or_null is not None and not self.VAL_NICKNAME.match(self.nickname_or_null):
            return '昵称格式错误，应为1到20字符'
        if self.qq_or_null is not None and not self.VAL_QQ.match(self.qq_or_null):
            return 'QQ号格式错误'
        if self.tel_or_null is not None and not self.VAL_TEL.match(self.tel_or_null):
            return '电话号码格式错误'
        if self.email_or_null is not None and not self.VAL_EMAIL.match(self.email_or_null):
            return '邮箱格式错误'
        if self.gender_or_null is not None and not self.VAL_GENDER.match(self.gender_or_null):
            return '选择的性别无效'
        if self.comment_or_null is not None and not self.VAL_COMMENT.match(self.comment_or_null):
            return '了解比赛的渠道格式错误'

        return None

    def __repr__(self) -> str:
        return f'[{self.nickname_or_null!r} qq={self.qq_or_null!r} email={self.email_or_null!r}]'