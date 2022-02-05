import asyncio

from src.logic.worker import Worker
from src import utils

if __name__=='__main__':
    utils.fix_zmq_asyncio_windows()
    worker = Worker('worker-test')
    asyncio.run(worker.run_forever())
