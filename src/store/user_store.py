from __future__ import annotations
from sqlalchemy import Column, String, JSON, Integer, ForeignKey, BigInteger, Boolean
from sqlalchemy.orm import relationship, validates
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

from . import Table
from .. import secret

if TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from . import UserProfileStore

class UserStore(Table):
    __tablename__ = 'user'

    WRITEUP_COOLDOWN_S = 60
    MAX_TOKEN_LEN = 512

    login_key: str = Column(String(192), nullable=False, unique=True)
    login_properties: Dict[str, Any] = Column(JSON, nullable=False)
    timestamp_ms = Column(BigInteger, nullable=False, default=lambda: int(1000*time.time()))

    enabled = Column(Boolean, nullable=False, default=True)
    group: str = Column(String(32), nullable=False)
    token: str = Column(String(MAX_TOKEN_LEN), nullable=True) # initialized in register logic
    auth_token: str = Column(String(128), nullable=True, unique=True, index=True) # initialized in register logic

    profile_id = Column(Integer, ForeignKey('user_profile.id'), nullable=True) # initialized in register logic
    profile: UserProfileStore = relationship('UserProfileStore', lazy='joined', foreign_keys=[profile_id])

    terms_agreed = Column(Boolean, nullable=False, default=False)
    last_feedback_ms = Column(BigInteger, nullable=True)

    GROUPS = {
        'staff': '工作人员',
        'banned': '已封禁',

        'admin_s': '网络安全管理员（在校学生）',
        'admin_f': '网络安全管理员（教职员工）',
        'pentest_s': '渗透测试员（在校学生）',
        'pentest_f': '渗透测试员（教职员工）',
        'dfir_s': '电子数据取证分析师（在校学生）',
        'dfir_f': '电子数据取证分析师（教职员工）',

    }
    TOT_BOARD_GROUPS = [k for k in GROUPS if k not in ['staff', 'banned']]

    def __repr__(self) -> str:
        nick = '(no profile)' if self.profile is None else self.profile.nickname_or_null
        login_key = self.login_key
        if len(login_key)>20:
            login_key = login_key[:18]+'...'
        return f'[U#{self.id} {login_key} {nick!r}]'

    @validates('token', 'auth_token', 'profile_id')
    def validate_not_null(self, key: str, new_value: Any) -> Any:
        old_value = getattr(self, key)
        if old_value is not None and new_value is None:
            raise ValueError(f'{key} should not be null')
        return new_value

    @validates('login_properties')
    def validate_login_properties(self, _key: str, login_properties: Any) -> Any:
        assert isinstance(login_properties, dict), 'login_properties should be a dict'
        assert 'type' in login_properties, 'login_properties should have a type'

        return login_properties

    def format_login_properties(self) -> str:
        #props = self.login_properties
        return ''

    def group_disp(self) -> str:
        g = self.group
        return self.GROUPS.get(g, f'({g})')

    def badges(self) -> List[str]:
        ret = []

        extra = self.login_properties.get('badges', None)
        if isinstance(extra, list):
            ret.extend(extra)

        return ret

    @property
    def writeup_path(self) -> Path:
        return secret.WRITEUP_PATH / str(self.id)

    @property
    def writeup_metadata_path(self) -> Path:
        return self.writeup_path / 'metadata.json'