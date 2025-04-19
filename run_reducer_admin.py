import asyncio
import threading
from gevent.pywsgi import WSGIServer

from src.logic.reducer import Reducer
from src.admin.app import app
from src import utils
from src import secret

reducer_started_event = threading.Event()

def reducer_thread(loop: asyncio.AbstractEventLoop, reducer: Reducer) -> None:
    async def task() -> None:
        await reducer._before_run()
        reducer_started_event.set()
        await reducer._mainloop()
        reducer.log('critical', 'run_reducer_admin.reducer_thread', 'reducer mainloop stopped')

    t = task()
    loop.create_task(t)
    loop.run_forever()

def admin_thread(loop: asyncio.AbstractEventLoop, reducer: Reducer) -> None:
    app.config['reducer_loop'] = loop
    app.config['reducer_obj'] = reducer
    reducer_started_event.wait()
    WSGIServer(secret.REDUCER_ADMIN_SERVER_ADDR, app, log=None).serve_forever()

if __name__=='__main__':
    utils.fix_zmq_asyncio_windows()

    l = asyncio.new_event_loop()
    r = Reducer('reducer')

    threading.Thread(target=admin_thread, args=(l, r), daemon=True).start()
    reducer_thread(l, r)