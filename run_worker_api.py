import multiprocessing
import os
from typing import List

import src.api.app

PROCS = 4
BASE_PORT = 8010

def process(idx: int) -> None:
    src.api.app.start(BASE_PORT+idx, f'worker#{idx}-{os.getpid()}')

if __name__=='__main__':
    ps: List[multiprocessing.Process]  = []

    for i in range(PROCS):
        p = multiprocessing.Process(target=process, args=(i,))
        ps.append(p)
        p.start()

    for p in ps:
        p.join()