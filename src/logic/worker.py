from __future__ import annotations
import zmq
from zmq.asyncio import Socket
import asyncio

from .base import StateContainerBase
from . import glitter
from .. import utils
from .. import secret

class Worker(StateContainerBase):
    RECOVER_INTERVAL_S = 3

    def __init__(self, process_name: str):
        super().__init__(process_name)

        self.action_socket: Socket = self.glitter_ctx.socket(zmq.REQ) # type: ignore
        self.event_socket: Socket = self.glitter_ctx.socket(zmq.SUB) # type: ignore

        self.action_socket.setsockopt(zmq.RCVTIMEO, glitter.CALL_TIMEOUT_MS)
        self.action_socket.setsockopt(zmq.SNDTIMEO, glitter.CALL_TIMEOUT_MS)
        self.action_socket.setsockopt(zmq.REQ_RELAXED, 1)
        self.event_socket.setsockopt(zmq.RCVTIMEO, glitter.SYNC_TIMEOUT_MS)
        self.event_socket.setsockopt(zmq.SNDTIMEO, glitter.SYNC_TIMEOUT_MS)

        self.action_socket.connect(secret.GLITTER_ACTION_SOCKET_ADDR)  # type: ignore
        self.event_socket.connect(secret.GLITTER_EVENT_SOCKET_ADDR)  # type: ignore
        self.event_socket.setsockopt(zmq.SUBSCRIBE, b'')

        self.state_counter: int = -1
        self.state_counter_cond: asyncio.Condition = asyncio.Condition()

    async def _sync_with_reducer(self, *, throttled: bool = True) -> None:
        self.game_dirty = True
        self.log('info', 'reducer.sync_with_reducer', 'sent handshake')

        while True:
            try:
                hello_res = await glitter.Action(
                    glitter.WorkerHelloReq(client=self.process_name, protocol_ver=glitter.PROTOCOL_VER)
                ).call(self.action_socket)
            except Exception as e:
                self.log('error', 'reducer.before_run',
                    f'exception during handshake, will try again: {utils.get_traceback(e)}')
                await asyncio.sleep(self.RECOVER_INTERVAL_S)
            else:
                if hello_res.error_msg is not None:
                    self.log('critical', 'worker.before_run', f'handshake failure: {hello_res.error_msg}')
                    raise RuntimeError(f'handshake failure: {hello_res.error_msg}')

                break

        self.log('info', 'worker.sync_with_reducer', f'begin sync')

        while True:
            try:
                event = await glitter.Event.next(self.event_socket)
                self.state_counter = event.state_counter
                self.log('info', 'worker.sync_with_reducer', f'got state counter {self.state_counter}')
                self.init_game()
                async with self.state_counter_cond:
                    self.state_counter_cond.notify_all()
            except Exception as e:
                self.log('error', 'worker.sync_with_reducer', f'exception during sync, will try again: {utils.get_traceback(e)}')
                await asyncio.sleep(self.RECOVER_INTERVAL_S)
            else:
                break

        self.log('debug', 'worker.sync_with_reducer', f'game state reconstructed')

        if throttled:
            await asyncio.sleep(self.RECOVER_THROTTLE_S)
        self.game_dirty = False

    async def _before_run(self) -> None:
        # reduce the possibility of losing initial event_socket packets
        # (we are still sound in this case, but some time is wasted waiting for next SYNC)
        await asyncio.sleep(.2)

        await self._sync_with_reducer(throttled=False)

    async def _mainloop(self) -> None:
        self.log('info', 'worker.mainloop', 'started to receive events')
        while True:
            try:
                cond = glitter.Event.next(self.event_socket)
                event = await asyncio.wait_for(cond, glitter.SYNC_TIMEOUT_MS/1000)
            except Exception as e:
                self.log('error', 'worker.mainloop', f'exception during event receive, will recover: {utils.get_traceback(e)}')
                await self._sync_with_reducer()
                continue

            if event.type!=glitter.EventType.SYNC:
                self.log('info', 'worker.mainloop', f'got event {event.type} ({event.state_counter})')

            # in rare cases when zeromq reaches high-water-mark, we may lose packets!
            if event.state_counter not in [self.state_counter, self.state_counter+1]:
                self.log('error', 'worker.mainloop', f'state counter mismatch, will recover: worker {self.state_counter} reducer {event.state_counter}')
                await self._sync_with_reducer()
            else:
                self.state_counter = event.state_counter
                await self.process_event(event)
                async with self.state_counter_cond:
                    self.state_counter_cond.notify_all()

    async def perform_action(self, req: glitter.ActionReq) -> glitter.ActionRep:
        self.log('info', 'worker.perform_action', f'call {req.type}')
        rep = await glitter.Action(req).call(self.action_socket)
        self.log('debug', 'worker.perform_action', f'called {req.type}, state counter is {rep.state_counter}')

        # sync state after call
        try:
            async with self.state_counter_cond:
                cond = self.state_counter_cond.wait_for(lambda: self.state_counter>=rep.state_counter)
                await asyncio.wait_for(cond, glitter.CALL_TIMEOUT_MS/1000)
        except asyncio.TimeoutError:
            self.log('error', 'worker.perform_action', f'state sync timeout: {self.state_counter} -> {rep.state_counter}')
            raise RuntimeError('timed out syncing state with reducer')

        self.log('debug', 'worker.perform_action', f'state counter synced to {self.state_counter}')
        return rep

    async def process_event(self, event: glitter.Event) -> None:
        if event.type!=glitter.EventType.SYNC:
            self.log('info', 'worker.process_event', f'got event {event.type}')
        await super().process_event(event)