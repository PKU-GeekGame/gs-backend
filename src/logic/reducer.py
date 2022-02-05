from __future__ import annotations
import zmq
from zmq.asyncio import Socket
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm.session import make_transient
import asyncio
from typing import Callable, Any, Awaitable

from . import glitter
from .base import StateContainerBase, make_callback_decorator
from ..store import *
from .. import utils
from .. import secret

on_action, action_listeners = make_callback_decorator()

class Reducer(StateContainerBase):
    def __init__(self, process_name: str):
        super().__init__(process_name)

        self.action_socket: Socket = self.glitter_ctx.socket(zmq.REP) # type: ignore
        self.event_socket: Socket = self.glitter_ctx.socket(zmq.PUB) # type: ignore

        self.action_socket.setsockopt(zmq.RCVTIMEO, glitter.CALL_TIMEOUT_MS)
        self.action_socket.setsockopt(zmq.SNDTIMEO, glitter.CALL_TIMEOUT_MS)
        self.event_socket.setsockopt(zmq.RCVTIMEO, glitter.SYNC_TIMEOUT_MS)
        self.event_socket.setsockopt(zmq.SNDTIMEO, glitter.SYNC_TIMEOUT_MS)

        self.action_socket.bind(secret.GLITTER_ACTION_SOCKET_ADDR) # type: ignore
        self.event_socket.bind(secret.GLITTER_EVENT_SOCKET_ADDR) # type: ignore

        self.state_counter: int = 1

    async def _before_run(self) -> None:
        self.log('info', 'reducer.before_run', 'started to initialize game')
        self.init_game()

    @on_action(glitter.ActionType.WORKER_HELLO)
    async def on_worker_hello(self, req: glitter.WorkerHelloReq) -> Optional[str]:
        client_ver = req.get('protocol_ver')
        if client_ver!=glitter.PROTOCOL_VER:
            return f'protocol version mismatch: worker {req["protocol_ver"]}, reducer {glitter.PROTOCOL_VER}'
        else:
            await self.emit_sync()
            return None

    @on_action(glitter.ActionType.REG_USER)
    async def on_reg_user(self, req: glitter.RegUserReq) -> Optional[str]:
        if (req['login_type'], req['login_identity']) in self._game.users.user_by_login_key:
            return 'user already exists'

        with self.SqlSession() as session:
            user = UserStore(
                login_type=req['login_type'],
                login_identity=req['login_identity'],
                login_peoperties=req['login_peoperties'],
                enabled=True,
                group=req['group'],
            )
            session.add(user)
            session.flush()
            uid = user.id
            assert uid is not None, 'created user not in db'

            profile = UserProfileStore(
                user_id=uid,
                # other metadata can be pre-filled here
            )
            session.add(profile)
            session.flush()
            assert profile.id is not None, 'created profile not in db'

            user.token = utils.sign_token(uid)
            user.profile_id = profile.id

            session.commit()
            self.state_counter += 1

        await self.emit_event(glitter.Event(glitter.EventType.UPDATE_USER, self.state_counter, uid))
        return None

    @on_action(glitter.ActionType.UPDATE_PROFILE)
    async def on_update_profile(self, req: glitter.UpdateProfileReq) -> Optional[str]:
        uid = int(req['uid'])
        with self.SqlSession() as session:
            user = session.execute(select(UserStore).where(UserStore.id==uid)).scalar()  # type: ignore
            if user is None:
                return 'user not found'

            # clone old profile

            profile = user.profile
            assert profile is not None, 'original profile not found for this user'

            session.expunge(profile)
            make_transient(profile)
            profile.id = None
            profile.timestamp_ms = None

            # write into db

            for k, v in profile.items():
                setattr(user, str(k), str(v))
            session.add(profile)
            session.flush()

            # link to the user

            assert profile.id is not None, 'updated profile not in db'
            user.profile_id = profile.id

            session.commit()
            self.state_counter += 1

        await self.emit_event(glitter.Event(glitter.EventType.UPDATE_USER, self.state_counter, uid))
        return None

    @on_action(glitter.ActionType.SUBMIT_FLAG)
    async def on_submit_flag(self, req: glitter.SubmitFlagReq) -> Optional[str]:
        with self.SqlSession() as session:
            submission = SubmissionStore(
                user_id=int(req['uid']),
                challenge_id=int(req['challenge_id']),
                flag=str(req['flag']),
            )
            session.add(submission)
            sid = submission.id
            assert sid is not None, 'created submission not in db'

            session.commit()
            self.state_counter += 1

        await self.emit_event(glitter.Event(glitter.EventType.NEW_SUBMISSION, self.state_counter, sid))
        return None

    async def handle_action(self, action: glitter.Action) -> Optional[str]:
        if action.req.get('ssrf_token')!=secret.GLITTER_SSRF_TOKEN:
            return f'packet validation failed'

        async def default(_self: Any, req: glitter.SomeActionReq) -> Optional[str]:
            return f'unknown action: {req["type"]}'

        listener: Callable[[Any, glitter.SomeActionReq], Awaitable[Optional[str]]] = action_listeners.get(action.req['type'], default)
        return await listener(self, action.req)

    async def emit_event(self, event: glitter.Event) -> None:
        self.log('info', 'reducer.emit_event', f'emit event {event.type}')
        await self.process_event(event)
        await event.send(self.event_socket)

    async def emit_sync(self) -> None:
        #self.log('debug', 'reducer.emit_sync', f'emit sync ({self.state_counter})')
        await glitter.Event(glitter.EventType.SYNC, self.state_counter, 0).send(self.event_socket)

    async def _mainloop(self) -> None:
        self.log('info', 'reducer.mainloop', 'started to receive actions')
        while True:
            try:
                future = glitter.Action.listen(self.action_socket)
                action: Optional[glitter.Action] = await asyncio.wait_for(future, glitter.SYNC_INTERVAL_S)
            except asyncio.TimeoutError:
                await self.emit_sync()
                continue
            except Exception as e:
                self.log('error', 'reducer.mainloop', f'exception during action receive, will try again: {e}')
                await self.emit_sync()
                await asyncio.sleep(glitter.SYNC_INTERVAL_S)
                continue

            if action is None:
                continue

            self.log('info', 'reducer.mainloop', f'got action {action.req["type"]}')

            old_counter = self.state_counter

            try:
                if action is None:
                    err: Optional[str] = 'malformed glitter packet'
                else:
                    err = await self.handle_action(action)

                if err is not None:
                    self.log('warning', 'reducer.handle_action', f'error: {err}')
            except Exception as e:
                self.log('critical', 'reducer.handle_action', f'exception, will report as interal error: {utils.get_traceback(e)}')
                err = 'internal error'

            if self.state_counter!=old_counter:
                self.log('debug', 'reducer.mainloop', f'state counter {old_counter} -> {self.state_counter}')
            assert self.state_counter-old_counter in [0, 1], 'action handler incremented state counter more than once'

            if action is not None:
                await action.reply({
                    'error_msg': err,
                    'state_counter': self.state_counter,
                }, self.action_socket)

            await self.emit_sync()