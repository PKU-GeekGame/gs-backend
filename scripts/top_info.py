import asyncio
from pathlib import Path
import sys

sys.path.append(str(Path('.').resolve()))

from src.logic.worker import Worker
from src.state import ScoreBoard
from src import utils

N_TOP = 30

if __name__=='__main__':
    utils.fix_zmq_asyncio_windows()

    worker = Worker('worker-test')
    asyncio.run(worker._before_run())

    b = worker.game.boards['score_pku']
    assert isinstance(b, ScoreBoard)

    print(*['SCORE', 'NAME', 'STU_ID', 'DEPT', 'TYPE', 'TEL', 'QQ'], sep='\t')
    for u, score in b.board[:N_TOP]:
        prop = u._store.login_properties
        prof = u._store.profile
        assert prop['type']=='iaaa'
        print(score, prop["info"]["name"], prop["info"]["identityId"], prop["info"]["dept"], prop["info"]["detailType"], prof.tel_or_null, prof.qq_or_null, sep='\t')