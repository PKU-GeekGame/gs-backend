from sqlalchemy import Column, Integer, String, Text, JSON
from sqlalchemy.orm import validates
import re
from typing import Any, Optional, Tuple

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

    VAL_FLAG = re.compile(r'^flag{[\x20-\x7c\x7e]{1,100}}$') # 0x7d is '}'
    MAX_FLAG_LEN = 110

    CAT_COLORS = {
        'Tutorial': '#333333',
        'Misc': '#7e2d86',
        'Web': '#2d8664',
        'Binary': '#864a2d',
        'Algorithm': '#2f2d86',
    }

    @validates('flags')
    def validate_flags(self, _key: str, flags: Any) -> Any:
        assert isinstance(flags, list), 'flags should be list'
        assert len(flags)>0, 'flags should not be empty'

        for flag in flags:
            assert isinstance(flag, dict), 'flag should be dict'

            assert 'name' in flag, 'flag should have name'
            assert 'type' in flag, 'flag should have type'
            assert 'val' in flag, 'flag should have val'
            assert 'base_score' in flag, 'flag should have base_score'

            assert flag['type'] in ['static', 'leet'], 'unknown flag type'
            assert isinstance(flag['val'], str), 'flag val should be str'
            assert isinstance(flag['name'], str), 'flag name should be str'
            assert isinstance(flag['base_score'], int), 'flag base_score should be int'

        return flags

    FLAG_SNIPPETS = {
        'static': '''{"name": "", "type": "static", "val" : "flag{}", "base_score": 100}''',
        'leet': '''{"name": "", "type": "leet", "val" : "flag{}", "salt": "", "base_score": 100}''',
    }

    @validates('actions')
    def validate_actions(self, _key: str, actions: Any) -> Any:
        assert isinstance(actions, list), 'actions should be list'

        for action in actions:
            assert isinstance(action, dict), 'action should be dict'

            assert 'name' in action, 'action should have name'
            assert 'type' in action, 'action should have type'
            assert isinstance(action['name'], str), 'action name should be str'
            assert isinstance(action['type'], str), 'action type should be str'

            if action['type']=='webpage':
                assert 'url' in action, 'webpage action should have url'
                assert isinstance(action['url'], str), 'webpage action url should be str'

            elif action['type']=='terminal':
                assert 'host' in action, 'terminal action should have host'
                assert 'port' in action, 'terminal action should have port'
                assert isinstance(action['host'], str), 'terminal action host should be str'
                assert isinstance(action['port'], int), 'terminal action port should be int'

            elif action['type']=='attachment':
                assert 'filename' in action, 'attachment action should have filename'
                assert isinstance(action['filename'], str), 'attachment action filename should be str'

        return actions

    ACTION_SNIPPETS = {
        'webpage': '''{"name": "题目网页", "type": "webpage", "url" : "https://"}''',
        'terminal': '''{"name": "题目", "type": "terminal", "host" : "", "port" : 0}''',
        'attachment': '''{"name": "题目附件", "type": "attachment", "filename" : ""}''',
    }

    @classmethod
    def check_submitted_flag(cls, flag: str) -> Optional[Tuple[str, str]]:
        if len(flag)>cls.MAX_FLAG_LEN:
            return 'FLAG_LEN', 'Flag过长'
        elif cls.VAL_FLAG.match(flag) is None:
            return 'FLAG_PATTERN', 'Flag格式错误'
        return None