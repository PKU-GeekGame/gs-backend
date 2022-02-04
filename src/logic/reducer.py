import zmq
from zmq.asyncio import Socket
from typing import Optional
from sqlalchemy import select
import asyncio

from . import glitter
from .base import StateContainerBase
from ..store import *
from .. import utils
from .. import secret

class Reducer(StateContainerBase):
    def __init__(self, process_name: str):
        super().__init__(process_name)

        self.action_socket: Socket = self.glitter_ctx.socket(zmq.REP) # type: ignore
        self.event_socket: Socket = self.glitter_ctx.socket(zmq.PUB) # type: ignore

        self.action_socket.setsockopt(zmq.RCVTIMEO, glitter.CALL_TIMEOUT_MS)
        self.action_socket.setsockopt(zmq.SNDTIMEO, glitter.CALL_TIMEOUT_MS)
        self.event_socket.setsockopt(zmq.RCVTIMEO, glitter.SYNC_TIMEOUT_MS)
        self.event_socket.setsockopt(zmq.SNDTIMEO, glitter.SYNC_TIMEOUT_MS)

        self.action_socket.connect(glitter.ACTION_SOCKET) # type: ignore
        self.event_socket.connect(glitter.EVENT_SOCKET) # type: ignore

        self.state_counter: int = 1

    async def _before_run(self) -> None:
        self.init_game()

    async def handle_action(self, action: glitter.Action) -> Optional[str]:
        if action.req.get('ssrf_token')!=secret.GLITTER_SSRF_TOKEN:
            return f'packet validation failed'

        if action.req['type']==glitter.ActionType.WORKER_HELLO:
            client_ver = action.req.get('protocol_ver')
            if client_ver!=glitter.PROTOCOL_VER:
                return f'protocol version mismatch: worker {action.req["protocol_ver"]}, reducer {glitter.PROTOCOL_VER}'
            else:
                return None

        elif action.req['type']==glitter.ActionType.REG_USER:
            with self.SqlSession() as session:
                user = UserStore(
                    login_type=action.req['login_type'],
                    login_identity=action.req['login_identity'],
                    login_peoperties=action.req['login_peoperties'],
                    enabled=True,
                    group=action.req['group'],
                )
                session.add(user)
                session.flush()
                uid = user.id
                assert uid is not None

                profile = UserProfileStore(
                    user_id=uid,
                    # other metadata can be pre-filled here
                )
                session.add(profile)
                session.flush()
                assert profile.id is not None

                user.token = utils.sign_token(uid)
                user.profile_id = profile.id

                session.commit()
                self.state_counter += 1

            await self.emit_event(glitter.Event(glitter.EventType.UPDATE_USER, self.state_counter, uid))
            return None

        elif action.req['type']==glitter.ActionType.UPDATE_PROFILE:
            uid = int(action.req['uid'])
            with self.SqlSession() as session:
                user = session.execute(select(UserStore).where(UserStore.id==uid)).scalar() # type: ignore
                if user is None:
                    return 'user not found'

                for k, v in action.req['profile'].items():
                    setattr(user, str(k), str(v))

                session.commit()
                self.state_counter += 1

            await self.emit_event(glitter.Event(glitter.EventType.UPDATE_USER, self.state_counter, uid))
            return None

        elif action.req['type']==glitter.ActionType.SUBMIT_FLAG:
            with self.SqlSession() as session:
                submission = SubmissionStore(
                    user_id=int(action.req['uid']),
                    challenge_id=int(action.req['challenge_id']),
                    flag=str(action.req['flag']),
                )
                session.add(submission)
                sid = submission.id
                assert sid is not None

                session.commit()
                self.state_counter += 1

            await self.emit_event(glitter.Event(glitter.EventType.NEW_SUBMISSION, self.state_counter, sid))
            return None

        else:
            return f'unknown action: {action.req["type"]}'

    async def emit_event(self, event: glitter.Event) -> None:
        self.process_event(event)
        await event.send(self.event_socket)

    async def emit_sync(self) -> None:
        await glitter.Event(glitter.EventType.SYNC, self.state_counter, 0).send(self.event_socket)

    async def _mainloop(self) -> None:
        while True:
            try:
                future = glitter.Action.listen(self.action_socket)
                action = await asyncio.wait_for(future, glitter.SYNC_INTERVAL_S)
            except asyncio.TimeoutError:
                await self.emit_sync()
                continue

            old_counter = self.state_counter

            try:
                if action is None:
                    err: Optional[str] = 'malformed glitter packet'
                else:
                    err = await self.handle_action(action)

                if err is not None:
                    self.log('warning', 'reducer.handle_action', f'error: {err}')
            except Exception as e:
                self.log('error', 'reducer.handle_action', f'exception: {utils.get_traceback(e)}')
                err = 'internal error'

            assert self.state_counter-old_counter in [0, 1]

            if action is not None:
                await action.reply({
                    'error_msg': err,
                    'state_counter': self.state_counter,
                })

            await self.emit_sync()