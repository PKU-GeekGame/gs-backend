from sqlalchemy import Column, Integer, ForeignKey, BigInteger, String
from sqlalchemy.orm import relationship
import time
import re
import hashlib
from typing import TYPE_CHECKING, Optional, Set
from unicategories import categories
import uniseg.graphemecluster
import emoji

if TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from . import UserStore
from . import Table

def unicode_chars(*cats: str) -> Set[str]:
    ret = set()
    for cat in cats:
        ret |= set(categories[cat].characters())
    return ret

class UserProfileStore(Table):
    __tablename__ = 'user_profile'

    UPDATE_COOLDOWN_S = 10
    MAX_INFO_LEN = 128

    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    user_: 'UserStore' = relationship('UserStore', lazy='select', foreign_keys=[user_id])
    timestamp_ms: int = Column(BigInteger, nullable=False, default=lambda: int(1000*time.time()))

    nickname_or_null = Column('nickname', String(MAX_INFO_LEN), nullable=True)
    VAL_NICKNAME = re.compile(r'^.{1,120}$')
    MAX_NICKNAME_UNICODE_LEN = 40

    qq_or_null = Column('qq', String(MAX_INFO_LEN), nullable=True)
    VAL_QQ = re.compile(r'^.{5,50}$')

    tel_or_null = Column('tel', String(MAX_INFO_LEN), nullable=True)
    VAL_TEL = re.compile(r'^.{5,20}$')

    email_or_null = Column('email', String(MAX_INFO_LEN), nullable=True)
    #VAL_EMAIL = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
    VAL_EMAIL = re.compile(r'^[a-z-]+[0-9]+@(mails?.)?tsinghua.edu.cn$')

    stuid_or_null = Column('stuid', String(MAX_INFO_LEN), nullable=True)
    VAL_STUID = re.compile(r'^\d{10}$')

    comment_or_null = Column('comment', String(MAX_INFO_LEN), nullable=True)
    VAL_COMMENT = re.compile(r'^.{0,100}$')

    PROFILE_FOR_GROUP = {
        'staff': ['nickname', 'tel', 'qq', 'comment'],
        'pku': ['nickname', 'tel', 'qq', 'comment'],
        'thu': ['nickname', 'email', 'qq', 'stuid', 'comment'],
        'other': ['nickname', 'qq', 'comment'],
        'banned': ['nickname', 'qq', 'comment'],
    }

    # https://unicode.org/reports/tr51/proposed.html
    EMOJI_CHARS = (
        {chr(0x200d)}  # zwj
        | {chr(0x200b)}  # zwsp, to break emoji componenets into independent chars
        | {chr(0x20e3)} # keycap
        | {chr(c) for c in range(0xfe00, 0xfe0f+1)} # variation selector
        | {chr(c) for c in range(0xe0020, 0xe007f+1)} # tag
        | {chr(c) for c in range(0x1f1e6, 0x1f1ff+1)} # regional indicator
    )

    # https://www.compart.com/en/unicode/category
    DISALLOWED_CHARS = (
        unicode_chars('Cc', 'Cf', 'Cs', 'Mc', 'Me', 'Mn', 'Zl', 'Zp') # control and modifier chars
        | {chr(c) for c in range(0x12423, 0x12431+1)} # too long
        | {chr(0x0d78)} # too long
    ) - EMOJI_CHARS
    WHITESPACE_CHARS = unicode_chars('Zs') | EMOJI_CHARS

    WIDE_CHARS = (
        {'w', 'm', '@', '%', '~', '=', '<', '>', '&'}
        | {chr(c) for c in range(ord('A'), ord('Z')+1)}
    )

    @classmethod
    def _deep_val_nickname(cls, name: str) -> Optional[str]:
        all_whitespace = True
        for c in name:
            if c in cls.DISALLOWED_CHARS:
                return f'昵称中不能包含字符 {hex(ord(c))}'
            if c not in cls.WHITESPACE_CHARS:
                all_whitespace = False

        if all_whitespace:
            return f'昵称不能全为空格'

        graphemes = list(uniseg.graphemecluster.grapheme_clusters(emoji.replace_emoji(name, '典')))
        unicode_len = sum(map((lambda g: 1 if (len(g)==1 and ord(g)<128 and g not in cls.WIDE_CHARS) else 2), graphemes))

        if unicode_len > cls.MAX_NICKNAME_UNICODE_LEN:
            return f'昵称长度（{unicode_len}）太长'

        return None

    def _deep_val_stuid(self, user: UserStore, stuid: str) -> Optional[str]:
        protocol , colon, idhash = user.login_key.partition(':')
        if colon!=':' or len(idhash)!=32 or protocol!='carsi':
            return '无法验证学号正确性'

        if hashlib.md5(stuid.encode()).hexdigest()!=idhash:
            return '学号与登录方式不符'

        return None

    def check_profile(self, user: UserStore) -> Optional[str]:
        group = user.group
        required_profiles = self.PROFILE_FOR_GROUP.get(group, [])

        for field in required_profiles:
            if getattr(self, f'{field}_or_null') is None:
                return f'个人信息不完整（{field}）'

        if 'nickname' in required_profiles:
            if not self.VAL_NICKNAME.match(self.nickname_or_null or ''):
                return '昵称格式错误'
            if (err := self._deep_val_nickname(self.nickname_or_null or '')) is not None:
                return err
        if 'qq' in required_profiles and not self.VAL_QQ.match(self.qq_or_null or ''):
            return 'QQ号格式错误'
        if 'tel' in required_profiles and not self.VAL_TEL.match(self.tel_or_null or ''):
            return '电话号码格式错误'
        if 'email' in required_profiles and not self.VAL_EMAIL.match(self.email_or_null or ''):
            return '邮箱格式错误，请填写清华邮箱地址'
        if 'stuid' in required_profiles:
            if not self.VAL_STUID.match(self.stuid_or_null or ''):
                return '学号格式错误'
            if (err := self._deep_val_stuid(user, self.stuid_or_null or '')) is not None:
                return err
        if 'comment' in required_profiles and not self.VAL_COMMENT.match(self.comment_or_null or ''):
            return '了解比赛的渠道格式错误'

        return None

    def __repr__(self) -> str:
        return f'[U#{self.user_id} P#{self.id} {self.nickname_or_null!r} qq={self.qq_or_null!r} email={self.email_or_null!r}]'