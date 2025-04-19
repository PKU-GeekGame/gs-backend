import httpx
from collections import deque
from typing import Dict, Deque, Optional
import time

from .. import utils
from .. import secret

class Pusher:
    THROTTLE_TIME_S = 20*60
    THROTTLE_N = 5

    def __init__(self) -> None:
        self.chan_history: Dict[str, Deque[float]] = {}

    async def push_message(self, msg: str, chan: Optional[str]) -> None:
        print('push message', chan)
        print(msg)
        if not secret.FEISHU_WEBHOOK_ADDR:
            return

        if chan:
            hist = self.chan_history.get(chan, None)
            if hist is None:
                hist = deque()
                self.chan_history[chan] = hist

            if len(hist) >= self.THROTTLE_N:
                if time.time() - hist[0] < self.THROTTLE_TIME_S:
                    print(f'push throttled ({chan}), time bound = {time.time()-hist[0]}')
                    return
                hist.popleft()

            hist.append(time.time())

        async with httpx.AsyncClient(http2=True) as client:
            try:
                await client.post(secret.FEISHU_WEBHOOK_ADDR, json={
                    'msg_type': 'text',
                    'content': {
                        'text': str(msg),
                    },
                })
            except Exception as e:
                print('PUSH MESSAGE FAILED', utils.get_traceback(e))
                pass