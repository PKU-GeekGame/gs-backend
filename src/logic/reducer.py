from __future__ import annotations
import zmq
from zmq.asyncio import Socket
from typing import Optional
from sqlalchemy import select
import asyncio
import time
from typing import Callable, Any, Awaitable

from . import glitter
from .base import StateContainerBase, make_callback_decorator
from ..state import Trigger
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
        await self.init_game(0)
        await self._update_tick()
        self.game_dirty = False

    @on_action(glitter.WorkerHelloReq)
    async def on_worker_hello(self, req: glitter.WorkerHelloReq) -> Optional[str]:
        client_ver = req.protocol_ver
        if client_ver!=glitter.PROTOCOL_VER:
            return f'protocol version mismatch: worker {req.protocol_ver}, reducer {glitter.PROTOCOL_VER}'
        else:
            await self.emit_sync()
            return None

    @on_action(glitter.RegUserReq)
    async def on_reg_user(self, req: glitter.RegUserReq) -> Optional[str]:
        if req.login_key in self._game.users.user_by_login_key:
            return 'user already exists'

        with self.SqlSession() as session:
            user = UserStore(
                login_key=req.login_key,
                login_properties=req.login_properties,
                enabled=True,
                group=req.group,
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
            user.auth_token = f'{uid}_{utils.gen_random_str(48, crypto=True)}'
            user.profile_id = profile.id

            session.commit()
            self.state_counter += 1

        await self.emit_event(glitter.Event(glitter.EventType.UPDATE_USER, self.state_counter, uid))
        return None

    @on_action(glitter.UpdateProfileReq)
    async def on_update_profile(self, req: glitter.UpdateProfileReq) -> Optional[str]:
        uid = int(req.uid)

        with self.SqlSession() as session:
            user: Optional[UserStore] = session.execute(select(UserStore).where(UserStore.id==uid)).scalar()  # type: ignore
            if user is None:
                return 'user not found'

            if 1000*time.time()-user.profile.timestamp_ms<1000:
                return '请求太频繁'

            # create profile

            profile = UserProfileStore(user_id=user.id)
            for k, v in req.profile.items():
                setattr(profile, f'{str(k)}_or_null', str(v))

            err = profile.check_profile(user.group)
            if err is not None:
                return err

            session.add(profile)
            session.flush()

            # link to the user

            assert profile.id is not None, 'updated profile not in db'
            user.profile_id = profile.id

            session.commit()
            self.state_counter += 1

        await self.emit_event(glitter.Event(glitter.EventType.UPDATE_USER, self.state_counter, uid))
        return None

    @on_action(glitter.AgreeTermReq)
    async def on_agree_term(self, req: glitter.AgreeTermReq) -> Optional[str]:
        uid = int(req.uid)

        with self.SqlSession() as session:
            user: Optional[UserStore] = session.execute(select(UserStore).where(UserStore.id==uid)).scalar()  # type: ignore
            if user is None:
                return 'user not found'

            user.terms_agreed = True
            session.commit()
            self.state_counter += 1

        await self.emit_event(glitter.Event(glitter.EventType.UPDATE_USER, self.state_counter, uid))
        return None

    @on_action(glitter.SubmitFlagReq)
    async def on_submit_flag(self, req: glitter.SubmitFlagReq) -> Optional[str]:
        ch = self._game.challenges.chall_by_id.get(int(req.challenge_id), None)
        if not ch:
            return 'challenge not found'

        with self.SqlSession() as session:
            submission = SubmissionStore(
                user_id=int(req.uid),
                challenge_key=ch._store.key,
                flag=str(req.flag),
            )
            session.add(submission)
            session.commit()
            self.state_counter += 1

            sid = submission.id
            assert sid is not None, 'created submission not in db'

        await self.emit_event(glitter.Event(glitter.EventType.NEW_SUBMISSION, self.state_counter, sid))

        sub = self._game.submissions.get(sid, None)
        assert sub is not None, 'submission not found'

        if sub.duplicate_submission:
            return '已经提交过此Flag'
        if sub.matched_flag is None:
            return 'Flag错误'

        return None

    async def _update_tick(self, ts: Optional[int] = None) -> int: # return: when it expires
        if ts is None:
            ts = int(time.time())

        old_tick = self._game.cur_tick
        new_tick, expires = self._game.trigger.get_tick_at_time(ts)

        self.log('info', 'reducer.update_tick', f'set tick {old_tick} -> {new_tick}')

        self._game.cur_tick = new_tick
        if new_tick!=old_tick:
            self.state_counter += 1
            await self.emit_event(glitter.Event(glitter.EventType.TICK_UPDATE, self.state_counter, new_tick))

        return expires

    async def _tick_updater_daemon(self) -> None:
        ts = time.time()
        while True:
            expires = await self._update_tick(int(ts))
            self.log('info', 'reducer.tick_updater_daemon', f'next tick in {"+INF" if expires==Trigger.TS_INF_S else int(expires-ts)} seconds')
            await asyncio.sleep(expires-ts+.2)
            ts = expires

    async def handle_action(self, action: glitter.Action) -> Optional[str]:
        async def default(_self: Any, req: glitter.ActionReq) -> Optional[str]:
            return f'unknown action: {req.type}'

        listener: Callable[[Any, glitter.ActionReq], Awaitable[Optional[str]]] = action_listeners.get(type(action.req), default)
        return await listener(self, action.req)

    async def emit_event(self, event: glitter.Event) -> None:
        self.log('info', 'reducer.emit_event', f'emit event {event.type}')
        await self.process_event(event)
        await event.send(self.event_socket)

    async def emit_sync(self) -> None:
        #self.log('debug', 'reducer.emit_sync', f'emit sync ({self.state_counter})')
        await glitter.Event(glitter.EventType.SYNC, self.state_counter, self._game.cur_tick).send(self.event_socket)

    async def _mainloop(self) -> None:
        self.log('info', 'reducer.mainloop', 'started to receive actions')
        _tick_updater_task = asyncio.create_task(self._tick_updater_daemon())

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

            self.log('info', 'reducer.mainloop', f'got action {action.req.type} from {action.req.client}')

            old_counter = self.state_counter

            try:
                if action is None:
                    err: Optional[str] = 'malformed glitter packet'
                else:
                    err = await self.handle_action(action)

                if err is not None:
                    self.log('warning', 'reducer.handle_action', f'error: {err}')
            except Exception as e:
                self.log('critical', 'reducer.handle_action', f'exception, will report as internal error: {utils.get_traceback(e)}')
                err = '内部错误，已记录日志'

            if self.state_counter!=old_counter:
                self.log('debug', 'reducer.mainloop', f'state counter {old_counter} -> {self.state_counter}')
            assert self.state_counter-old_counter in [0, 1], 'action handler incremented state counter more than once'

            if action is not None:
                await action.reply(glitter.ActionRep(error_msg=err, state_counter=self.state_counter),self.action_socket)

            await self.emit_sync()