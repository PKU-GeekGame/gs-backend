import asyncio
from pathlib import Path
import sys
from collections import Counter

sys.path.append(str(Path('.').resolve()))

from src.logic.worker import Worker
from src import utils

if __name__=='__main__':
    utils.fix_zmq_asyncio_windows()

    worker = Worker('worker-test')
    asyncio.run(worker._before_run())

    cat_board = {}

    for u in worker.game.users.list:
        if u._store.group=='pku':
            cat_score = Counter()
            cat_flags = {}
            for sub in u.submissions:
                f = sub.matched_flag
                if f:
                    cat = sub.challenge._store.category
                    cat_score[cat] += sub.gained_score()
                    cat_flags.setdefault(cat, []).append(f'{f.challenge._store.title} / {f.name or "--"}')

            for cat, score in cat_score.items():
                cat_board.setdefault(cat, []).append([
                    score,
                    u._store.profile.nickname_or_null,
                    u._store.login_key,
                    u._store.format_login_properties(),
                    cat_flags[cat],
                ])

    for cat, li in cat_board.items():
        li = sorted(li, key=lambda x: -x[0])
        print('==', cat)
        for row in li[:10]:
            print(*row, sep='\t')
