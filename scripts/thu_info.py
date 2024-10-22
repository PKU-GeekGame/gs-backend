import asyncio
from pathlib import Path
import sys

sys.path.append(str(Path('.').resolve()))

from src.logic.worker import Worker
from src.state import ScoreBoard, FirstBloodBoard
from src import utils

if __name__=='__main__':
    utils.fix_zmq_asyncio_windows()

    worker = Worker('worker-test')
    asyncio.run(worker._before_run())

    b = worker.game.boards['score_thu']
    assert isinstance(b, ScoreBoard)
    b._update_board()

    flags = [(f'{ch._store.key}[{idx}]', f) for ch in worker.game.challenges.list for idx, f in enumerate(ch.flags)]

    print(*['RANK', 'SCORE', 'UID', 'NICKNAME', 'STU_ID', 'ROOKIE', 'EMAIL', 'QQ'] + [f[0] for f in flags], sep='\t')

    rookies = []
    for ind, (u, score) in enumerate(b.board):
        prop = u._store.login_properties
        prof = u._store.profile
        rookie = 'rookie' in u._store.badges()

        assert prop['type']=='carsi'
        assert '\t' not in prof.nickname_or_null

        row = [ind+1, score, u._store.id, prof.nickname_or_null, prof.stuid_or_null, 'YES' if rookie else '', prof.email_or_null, prof.qq_or_null]
        flag_res = []
        for _key, f in flags:
            if f in u.passed_flags:
                flag_res.append(u.passed_flags[f].gained_score())
            else:
                flag_res.append('')
        print(*(row + flag_res), sep='\t')
