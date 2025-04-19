import asyncio
from pathlib import Path
import sys
import json

sys.path.append(str(Path('.').resolve()))

from src.logic.worker import Worker
from src.state import ScoreBoard, FirstBloodBoard
from src import utils

MIN_SCORE = 200

if __name__=='__main__':
    ret = []

    utils.fix_zmq_asyncio_windows()

    worker = Worker('worker-test')
    asyncio.run(worker._before_run())

    for u in worker.game.users.list:
        if u.tot_score>MIN_SCORE:
            ret.append(u._store.login_key)

    print(ret)
    print(len(ret))
    with open('active_players.json', 'w') as f:
        json.dump(ret, f)
