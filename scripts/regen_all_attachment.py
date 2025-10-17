import asyncio
from pathlib import Path
import sys
import time

sys.path.append(str(Path('.').resolve()))

from src.logic.worker import Worker
from src.api.endpoint.attachment import gen_attachment
from src import utils

def log(level: utils.LogLevel, module: str, message: str) -> None:
    if level not in ['debug', 'info']:
        print(f' [{level}] {module}: {message}')

if __name__=='__main__':
    utils.fix_zmq_asyncio_windows()

    worker = Worker('worker-test')
    asyncio.run(worker._before_run())

    for ch in worker.game.challenges.list:
        for fn, att in ch.attachments.items():
            if att['type']=='dyn_attachment':
                print('===', ch._store.key, '/', fn)
                times = []
                for u in worker.game.users.list:
                    if u.check_play_game() is None:
                        t1 = time.time()
                        url = gen_attachment(ch, att, u, log, True)
                        t2 = time.time()
                        times.append(t2-t1)
                        if url is None:
                            sys.exit(1)

                times = sorted(times)
                print(f'avg: {sum(times)/len(times):.4f} / p99: {times[int(len(times)*0.99)]:.4f}')