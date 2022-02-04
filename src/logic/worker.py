from __future__ import annotations
import zmq
from zmq.asyncio import Socket
import asyncio

from .base import StateContainerBase
from . import glitter
from .. import secret

class Worker(StateContainerBase):
    def __init__(self, process_name: str):
        super().__init__(process_name)

        self.action_socket: Socket = self.glitter_ctx.socket(zmq.REQ) # type: ignore
        self.event_socket: Socket = self.glitter_ctx.socket(zmq.SUB) # type: ignore

        self.action_socket.setsockopt(zmq.RCVTIMEO, glitter.CALL_TIMEOUT_MS)
        self.action_socket.setsockopt(zmq.SNDTIMEO, glitter.CALL_TIMEOUT_MS)
        self.event_socket.setsockopt(zmq.RCVTIMEO, glitter.SYNC_TIMEOUT_MS)
        self.event_socket.setsockopt(zmq.SNDTIMEO, glitter.SYNC_TIMEOUT_MS)

        self.action_socket.connect(glitter.ACTION_SOCKET) # type: ignore
        self.event_socket.connect(glitter.EVENT_SOCKET) # type: ignore
        self.event_socket.setsockopt(zmq.SUBSCRIBE, b'')

        self.state_counter: int = -1
        self.state_counter_cond: asyncio.Condition = asyncio.Condition()

    async def _sync_with_reducer(self) -> None:
        event = await glitter.Event.next(self.event_socket)
        self.state_counter = event.state_counter
        self.init_game()
        self.state_counter_cond.notify_all()

    async def _before_run(self) -> None:
        hello_res = await glitter.Action({
            'type': glitter.ActionType.WORKER_HELLO,
            'ssrf_token': secret.GLITTER_SSRF_TOKEN,
            'protocol_ver': glitter.PROTOCOL_VER,
        }).call(self.action_socket)

        if hello_res['error_msg'] is not None:
            self.log('critical', 'worker.before_run', f'handshake failure: {hello_res["error_msg"]}')
            raise RuntimeError(f'handshake failure: {hello_res["error_msg"]}')

        await self._sync_with_reducer()

    async def _mainloop(self) -> None:
        while True:
            event = await glitter.Event.next(self.event_socket)

            # in rare cases when zeromq reaches high-water-mark, we may lose packets!
            if event.state_counter not in [self.state_counter, self.state_counter+1]:
                await self._sync_with_reducer()
            else:
                self.state_counter = event.state_counter
                self.process_event(event)
                self.state_counter_cond.notify_all()

    async def perform_action(self, req: glitter.SomeActionReq) -> glitter.ActionRep:
        rep = await glitter.Action(req).call(self.action_socket)

        cond = self.state_counter_cond.wait_for(lambda: self.state_counter>=rep['state_counter'])
        try:
            await asyncio.wait_for(cond, glitter.CALL_TIMEOUT_MS/1000)
        except asyncio.TimeoutError:
            self.log('error', 'worker.perform_action', f'state sync timeout: {self.state_counter} -> {rep["state_counter"]}')
            raise RuntimeError('timed out syncing state with reducer')

        return rep