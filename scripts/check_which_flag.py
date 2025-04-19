import asyncio
from pathlib import Path
import sys

sys.path.append(str(Path('.').resolve()))

from src.logic.worker import Worker
from src import utils

TARGET_KEY = 'xxx'
TARGET_IDX = 0
TARGET_FLAG = 'xxx'

if __name__=='__main__':
    utils.fix_zmq_asyncio_windows()

    worker = Worker('worker-test')
    asyncio.run(worker._before_run())

    ch = worker.game.challenges.chall_by_key[TARGET_KEY]
    f = ch.flags[TARGET_IDX]
    for u in worker.game.users.list:
        if f.correct_flag(u)==TARGET_FLAG:
            print(u)