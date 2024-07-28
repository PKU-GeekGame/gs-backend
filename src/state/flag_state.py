from __future__ import annotations
import hashlib
import string
from functools import lru_cache
from typing import TYPE_CHECKING, Set, Dict, Any, Union, List, Callable, Tuple, Optional

if TYPE_CHECKING:
    from . import Game, Challenge, User, Submission
from . import WithGameLifecycle
from ..store import UserStore
from .. import utils
from .. import secret

def leet_flag(flag: str, token: str, salt: str) -> str:
    uid = int(hashlib.sha256((token+salt).encode()).hexdigest(), 16)
    rcont = flag[len('flag{'):-len('}')]
    rdlis=[]

    for i in range(len(rcont)):
        if rcont[i] in string.ascii_letters:
            rdlis.append(i)

    rdseed=(uid+233)*114547%123457
    for it in range(4):
        if not rdlis:  # no any leetable chars
            return flag

        np = rdseed%len(rdlis)
        npp = rdlis[np]
        rdseed = (rdseed+233)*114547%123457
        del rdlis[np]
        px = rcont[npp]
        rcont = rcont[:npp] + (px.upper() if px in string.ascii_lowercase else px.lower()) + rcont[npp+1:]

    return 'flag{'+rcont+'}'

def dyn_flag(flag: Flag, user: User) -> str:
    assert isinstance(flag.val, str)
    mod_path = secret.ATTACHMENT_PATH / flag.val

    with utils.chdir(mod_path):
        gen_mod = utils.load_module(mod_path / 'flag.py')
        gen_fn: Callable[[User, Flag], str] = gen_mod.flag
        out_flag = gen_fn(user, flag)
        assert isinstance(out_flag, str), f'gen_fn must return a str, got {type(out_flag)}'

    return out_flag

class Flag(WithGameLifecycle):
    def __init__(self, game: Game, descriptor: Dict[str, Any], chall: Challenge, idx0: int):
        self._game: Game = game
        self._store: Dict[str, Any] = descriptor

        self.challenge = chall
        self.idx0 = idx0
        self.type: str = descriptor['type']
        self.val: Union[str, List[str]] = descriptor['val'] # list[str] for partitioned
        self.name: str = descriptor['name']
        self.salt: str = descriptor.get('salt', '')
        self.base_score: int = descriptor['base_score']

        self.cur_score: int = 0
        self.score_history: List[Tuple[int, int]] = []

        self.passed_users: Set[User] = set()
        self.passed_users_for_score_calculation: Set[User] = set()

    def _calc_cur_score(self) -> int:
        u = len(self.passed_users_for_score_calculation)
        return int(self.base_score * (.4 + .6 * (.98**u)))

    def _update_cur_score(self, sub: Submission) -> None:
        new_score = self._calc_cur_score()
        if self.cur_score != new_score:
            self.cur_score = new_score
            self.score_history.append((sub._store.id, new_score))

    @lru_cache(maxsize=None)
    def correct_flag(self, user: User) -> str:
        try:
            if self.type=='static':
                assert isinstance(self.val, str)
                return self.val
            elif self.type=='leet':
                assert isinstance(self.val, str)
                return leet_flag(self.val, user._store.token, self.salt)
            elif self.type=='partitioned':
                assert isinstance(self.val, list)
                return self.val[user.get_partition(self.challenge, len(self.val))]
            elif self.type=='dynamic':
                return dyn_flag(self, user)
            else:
                raise ValueError(f'Unknown flag type: {self.type}')
        except Exception as e:
            self._game.worker.log('error', 'flag.correct_flag', f'error calculating flag {repr(self)} for U#{user._store.id}: {utils.get_traceback(e)}')
            return '😅FAIL'

    def validate_flag(self, user: User, flag: str) -> bool:
        return flag==self.correct_flag(user)

    def on_scoreboard_reset(self) -> None:
        self.cur_score = self.base_score
        self.score_history = [(0, self.base_score)]

        self.passed_users = set()
        self.passed_users_for_score_calculation = set()

    def on_scoreboard_update(self, submission: Submission, in_batch: bool) -> None:
        assert submission.matched_flag is self # always true as delegated from Challenge

        self.passed_users.add(submission.user)

        if (
            submission.user._store.group in UserStore.MAIN_BOARD_GROUPS # user is in main board
            and submission._store.precentage_override_or_null is None # submission not in second phase
        ):
            self.passed_users_for_score_calculation.add(submission.user)

        self._update_cur_score(submission)

    def __repr__(self) -> str:
        return f'[{self.challenge._store.key}#{self.idx0+1}]'

    def is_user_deducted(self, user: User) -> bool:
        sub = user.passed_flags.get(self, None)
        if sub and (
            sub._store.precentage_override_or_null is not None
            or sub._store.score_override_or_null is not None
        ):
            return True
        else:
            return False

    def user_status(self, user: Optional[User]) -> str:
        if user and user in self.passed_users:
            return 'passed' + ('-deducted' if self.is_user_deducted(user) else '')
        else:
            return 'untouched'

    def describe_json(self, user: Optional[User]) -> Dict[str, Any]:
        return {
            'name': self.name,
            'base_score': self.base_score,
            'cur_score': self.cur_score,
            'passed_users_count': len(self.passed_users),
            'status': self.user_status(user),
        }