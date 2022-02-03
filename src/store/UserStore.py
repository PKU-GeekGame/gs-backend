from sqlalchemy import Column, String, UniqueConstraint, JSON, Integer, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship

from . import Table, UserProfileStore

class UserStore(Table):
    __tablename__ = 'user'

    MAX_TOKEN_LEN = 512

    login_type = Column(String(32), nullable=False)
    login_identity = Column(String(128), nullable=False)
    login_properties = Column(JSON, nullable=False)

    enabled = Column(Boolean, nullable=False, default=True)
    group = Column(String(32), nullable=False)
    token = Column(String(MAX_TOKEN_LEN), nullable=True) # initialized in register logic

    admin_token_or_null = Column(String(64), nullable=True)

    profile_id = Column(Integer, ForeignKey('user_profile.id'), nullable=True) # initialized in register logic
    profile = relationship('UserProfileStore', lazy='joined', foreign_keys=[profile_id])
    terms_agreed = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint('login_type', 'login_identity'),
        Index('admin_token_index', admin_token_or_null, unique=True),
    )

    def __repr__(self) -> str:
        nick = '(no profile)' if self.profile is None else self.profile.nickname_or_null
        return f'<#{self.id} {self.login_type} {self.login_identity}: {nick!r}>'