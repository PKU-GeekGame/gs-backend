import asyncio
import os

from src.logic.reducer import Reducer
from src import utils

if __name__=='__main__':
    utils.fix_zmq_asyncio_windows()
    reducer = Reducer(f'reducer-{os.getpid()}')
    asyncio.run(reducer.run_forever())