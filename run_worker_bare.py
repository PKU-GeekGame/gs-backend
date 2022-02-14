import asyncio
import threading

from src.logic.worker import Worker
from src import utils

def worker_thread(w: Worker) -> None:
    asyncio.run(w.run_forever())
    print('-- worker stopped --')

if __name__=='__main__':
    utils.fix_zmq_asyncio_windows()

    worker = Worker('worker-test')
    threading.Thread(target=worker_thread, args=(worker,), daemon=False).start()

    # worker is run in a separate thread, so users can use `-i` to start a REPL and inspect it