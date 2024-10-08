import asyncio
from pathlib import Path
import sys

sys.path.append(str(Path('.').resolve()))

from src.logic.worker import Worker
from src.api.endpoint.attachment import gen_attachment
from src import utils

def log(level: utils.LogLevel, module: str, message: str) -> None:
    print(f' [{level}] {module}: {message}')

if __name__=='__main__':
    utils.fix_zmq_asyncio_windows()

    worker = Worker('worker-test')
    asyncio.run(worker._before_run())

    for ch in worker.game.challenges.list:
        for fn, att in ch.attachments.items():
            if att['type']=='dyn_attachment':
                print('===', ch._store.key, '/', fn)
                for u in worker.game.users.list:
                    if u.check_play_game() is None:
                        url = gen_attachment(ch, att, u, log, True)
                        if url is None:
                            sys.exit(1)