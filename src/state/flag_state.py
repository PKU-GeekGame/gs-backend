from __future__ import annotations
import re
import hashlib
import string
from functools import lru_cache
from typing import TYPE_CHECKING, Set, Dict, Any

if TYPE_CHECKING:
    from . import Game, Challenge, User, Submission
from . import WithGameLifecycle
from .. import secret

def leet_flag(flag: str, uid: int) -> str:
    uid = int(hashlib.sha256((secret.FLAG_LEET_SALT+str(uid)).encode()).hexdigest(), 16)
    rcont = flag[len('flag{'):-len('}')]
    rdlis=[]
    for i in range(len(rcont)):
        if rcont[i] in string.ascii_letters:
            rdlis.append(i)

    rdseed=(uid+233)*114547%123457
    for it in range(2):
        np = rdseed%len(rdlis)
        npp = rdlis[np]
        rdseed = (rdseed+233)*114547%123457
        del rdlis[np]
        px = rcont[npp]
        rcont = rcont[:npp] + (px.upper() if px in string.ascii_lowercase else px.lower()) + rcont[npp+1:]

    return 'flag{'+rcont+'}'

class Flag(WithGameLifecycle):
    TYPES = ['static', 'leet']
    VAL_FLAG = re.compile(r'^flag{[\x20-\x7e]{0,100}}$') # todo: move check to reducer or api
    MAX_FLAG_LEN = 110

    def __init__(self, game: Game, descriptor: Dict[str, Any], chall: Challenge, idx: int):
        self._game: Game = game
        self._store: Dict[str, Any] = descriptor

        self.challenge = chall
        self.idx = idx
        self.type: str = descriptor['type']
        self.val: str = descriptor['val']
        self.base_score: int = descriptor['base_score']

        self.cur_score: int = 0
        self.passed_users: Set[User] = set()

    def _update_cur_score(self) -> None:
        u = max(0, len(self.passed_users)-1)
        self.cur_score = int(self.base_score * (.4 + .6 * (.98**u)))

    @lru_cache(maxsize=512)
    def correct_flag(self, user: User) -> str:
        if self.type=='static':
            return self.val
        elif self.type=='leet':
            return leet_flag(self.val, user._store.id)
        else:
            raise ValueError(f'Unknown flag type: {self.type}')

    def validate_flag(self, user: User, flag: str) -> bool:
        if len(flag)>self.MAX_FLAG_LEN or not self.VAL_FLAG.match(flag):
            return False

        return flag==self.correct_flag(user)

    def on_scoreboard_reset(self) -> None:
        self.cur_score = self.base_score
        self.passed_users = set()
        self._update_cur_score()

    def on_scoreboard_update(self, submission: Submission, in_batch: bool) -> None:
        if submission.matched_flag is self:
            self.passed_users.add(submission.user)
            self._update_cur_score()

    def __repr__(self) -> str:
        return f'[{self.challenge._store.key}#{self.idx}]'