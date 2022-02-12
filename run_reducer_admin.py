import asyncio
import os
import threading

from src.logic.reducer import Reducer
from src.admin.app import app
from src import utils

ADMIN_PORT = 5000

reducer_started_event = threading.Event()

def reducer_thread(loop: asyncio.AbstractEventLoop, reducer: Reducer):
    async def task():
        await reducer._before_run()
        reducer_started_event.set()
        await reducer._mainloop()
        reducer.log('critical', 'run_reducer_admin.reducer_thread', 'reducer mainloop stopped')

    t = task()
    loop.create_task(t)
    loop.run_forever()

if __name__=='__main__':
    utils.fix_zmq_asyncio_windows()

    l = asyncio.new_event_loop()
    r = Reducer(f'reducer-{os.getpid()}')
    threading.Thread(target=reducer_thread, args=(l, r), daemon=True).start()

    reducer_started_event.wait()

    app.config['reducer_loop'] = l
    app.config['reducer_obj'] = r
    app.run(host='127.0.0.1', port=ADMIN_PORT, debug=False)