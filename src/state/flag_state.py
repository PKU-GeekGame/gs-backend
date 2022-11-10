from __future__ import annotations
import hashlib
import string
from functools import lru_cache
from typing import TYPE_CHECKING, Set, Dict, Any, Union, List

if TYPE_CHECKING:
    from . import Game, Challenge, User, Submission
from . import WithGameLifecycle
from ..store import UserStore

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
        self.passed_users: Set[User] = set()
        self.passed_users_for_score_calculation: Set[User] = set()

    def _update_cur_score(self) -> None:
        u = len(self.passed_users_for_score_calculation)
        self.cur_score = int(self.base_score * (.4 + .6 * (.98**u)))

    @lru_cache(maxsize=4096)
    def correct_flag(self, user: User) -> str:
        if self.type=='static':
            return self.val  # type: ignore
        elif self.type=='leet':
            return leet_flag(self.val, user._store.token, self.salt)  # type: ignore
        elif self.type=='partitioned':
            return self.val[user.get_partition(self.challenge, len(self.val))]
        else:
            raise ValueError(f'Unknown flag type: {self.type}')

    def validate_flag(self, user: User, flag: str) -> bool:
        return flag==self.correct_flag(user)

    def on_scoreboard_reset(self) -> None:
        self.cur_score = self.base_score
        self.passed_users = set()
        self.passed_users_for_score_calculation = set()
        self._update_cur_score()

    def on_scoreboard_update(self, submission: Submission, in_batch: bool) -> None:
        if submission.matched_flag is self:
            self.passed_users.add(submission.user)
            if (
                submission.user._store.group in UserStore.MAIN_BOARD_GROUPS # user is in main board
                and submission._store.precentage_override_or_null is None # submission not in second phase
            ):
                self.passed_users_for_score_calculation.add(submission.user)
            self._update_cur_score()

    def __repr__(self) -> str:
        return f'[{self.challenge._store.key}#{self.idx0+1}]'

    def describe_json(self, user: User) -> Dict[str, Any]:
        return {
            'name': self.name,
            'base_score': self.base_score,
            'cur_score': self.cur_score,
            'passed_users_count': len(self.passed_users),
            'status': 'passed' if user in self.passed_users else 'untouched',
        }