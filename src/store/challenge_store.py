from sqlalchemy import Column, Integer, String, Text, JSON
from sqlalchemy.orm import validates
from typing import Any

from . import Table

class ChallengeStore(Table):
    __tablename__ = 'challenge'

    effective_after = Column(Integer, nullable=False)

    key = Column(String(32), nullable=False, unique=True)
    title = Column(String(64), nullable=False)
    category = Column(String(32), nullable=False)
    sorting_index = Column(Integer, nullable=False)
    desc_template = Column(Text, nullable=False)

    actions = Column(JSON, nullable=False)
    flags = Column(JSON, nullable=False)

    @validates('flags')
    def validate_flags(self, _key: str, flags: Any) -> Any:
        assert isinstance(flags, list), 'flags should be list'

        for flag in flags:
            assert isinstance(flag, dict), 'flag should be dict'

            assert 'type' in flag, 'flag should have type'
            assert 'val' in flag, 'flag should have val'
            assert 'name' in flag, 'flag should have name'
            assert 'base_score' in flag, 'flag should have base_score'

            assert isinstance(flag['type'], str), 'flag type should be str'
            assert isinstance(flag['val'], str), 'flag val should be str'
            assert isinstance(flag['name'], str), 'flag name should be str'
            assert isinstance(flag['base_score'], int), 'flag base_score should be int'

        return flags

    @validates('actions')
    def validate_actions(self, _key: str, actions: Any) -> Any:
        assert isinstance(actions, list), 'actions should be list'

        for action in actions:
            assert isinstance(action, dict), 'action should be dict'

            # todo: what is in an action?

        return actions