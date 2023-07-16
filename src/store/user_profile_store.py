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
    user_: 'UserStore' = relationship('UserStore', lazy='select', foreign_keys=[user_id])
    timestamp_ms: int = Column(BigInteger, nullable=False, default=lambda: int(1000*time.time()))

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
        'staff': ['nickname', 'gender', 'tel', 'qq', 'comment'],
        'pku': ['nickname', 'gender', 'tel', 'qq', 'comment'],
        'other': ['nickname', 'qq', 'comment'],
        'banned': ['nickname', 'qq', 'comment'],
    }

    @staticmethod
    def _deep_val_nickname(name: str) -> Optional[str]:
        invalids = {
            '\u200B', '\u200C', '\u200D', '\u200E', '\u200F',
            '\u202A', '\u202B', '\u202C', '\u202D', '\u202E',
            '\u2060', '\u2061', '\u2062', '\u2063', '\u2064', '\u2065', '\u2066', '\u2067', '\u2068',
            '\u2069', '\u206A', '\u206B', '\u206C', '\u206D', '\u206E', '\u206F'
        }
        whitespaces = {
            '\u0009', '\u0020', '\u00A0', '\u2000', '\u2001', '\u2002', '\u2003', '\u2004', '\u2005', '\u2006', '\u2007',
            '\u2008', '\u2009', '\u200A', '\u202F', '\u205F', '\u3000', '\u200B', '\u200C', '\u200D', '\u2060', '\uFEFF',
        }

        for c in invalids:
            if c in name:
                return f'昵称不能包含非法字符（{c!r}）'

        if all(c in whitespaces for c in name):
            return f'昵称不能全为空格'

        return None

    def check_profile(self, group: str) -> Optional[str]:
        required_profiles = self.PROFILE_FOR_GROUP.get(group, [])

        for field in required_profiles:
            if getattr(self, f'{field}_or_null') is None:
                return f'个人信息不完整（{field}）'

        if 'nickname' in required_profiles and not self.VAL_NICKNAME.match(self.nickname_or_null or ''):
            return '昵称格式错误，应为1到20字符'
        if (err := self._deep_val_nickname(self.nickname_or_null or '')) is not None:
            return err
        if 'qq' in required_profiles and not self.VAL_QQ.match(self.qq_or_null or ''):
            return 'QQ号格式错误'
        if 'tel' in required_profiles and not self.VAL_TEL.match(self.tel_or_null or ''):
            return '电话号码格式错误'
        if 'email' in required_profiles and not self.VAL_EMAIL.match(self.email_or_null or ''):
            return '邮箱格式错误'
        if 'gender' in required_profiles and not self.VAL_GENDER.match(self.gender_or_null or ''):
            return '选择的性别无效'
        if 'comment' in required_profiles and not self.VAL_COMMENT.match(self.comment_or_null or ''):
            return '了解比赛的渠道格式错误'

        return None

    def __repr__(self) -> str:
        return f'[U#{self.user_id} P#{self.id} {self.nickname_or_null!r} qq={self.qq_or_null!r} email={self.email_or_null!r}]'