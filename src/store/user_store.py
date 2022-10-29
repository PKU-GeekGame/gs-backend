from __future__ import annotations
from sqlalchemy import Column, String, JSON, Integer, ForeignKey, BigInteger, Boolean
from sqlalchemy.orm import relationship, validates
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from . import UserProfileStore
from . import Table

class UserStore(Table):
    __tablename__ = 'user'

    MAX_TOKEN_LEN = 512

    login_key: str = Column(String(192), nullable=False, unique=True)
    login_properties = Column(JSON, nullable=False)
    timestamp_ms = Column(BigInteger, nullable=False, default=lambda: int(1000*time.time()))

    enabled = Column(Boolean, nullable=False, default=True)
    group: str = Column(String(32), nullable=False)
    token = Column(String(MAX_TOKEN_LEN), nullable=True) # initialized in register logic
    auth_token = Column(String(128), nullable=True, unique=True, index=True) # initialized in register logic

    profile_id = Column(Integer, ForeignKey('user_profile.id'), nullable=True) # initialized in register logic
    profile: UserProfileStore = relationship('UserProfileStore', lazy='joined', foreign_keys=[profile_id])
    terms_agreed = Column(Boolean, nullable=False, default=False)

    GROUPS = {
        'pku': '北京大学',
        'other': '校外选手',
        'staff': '工作人员',
        'banned': '已封禁',
    }

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

    def group_disp(self) -> str:
        g = self.group
        return self.GROUPS.get(g, f'({g})')