import multiprocessing
from typing import List

import src.api.app
import src.police
import src.secret

def process(idx0: int) -> None:
    src.api.app.start(idx0, f'worker#{idx0}')

if __name__=='__main__':
    ps: List[multiprocessing.Process]  = []

    for i in range(src.secret.N_WORKERS):
        p = multiprocessing.Process(target=process, args=(i,))
        ps.append(p)
        p.start()

    if src.secret.POLICE_ENABLED:
        p = multiprocessing.Process(target=src.police.police_process, args=())
        ps.append(p)
        p.start()

    for p in ps:
        p.join()