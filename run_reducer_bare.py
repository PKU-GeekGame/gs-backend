import asyncio

from src.logic.reducer import Reducer
from src import utils

if __name__=='__main__':
    utils.fix_zmq_asyncio_windows()
    reducer = Reducer('reducer')
    asyncio.run(reducer.run_forever())