from __future__ import annotations
import zmq
from zmq.asyncio import Socket
from typing import Optional
from sqlalchemy import select
import asyncio
import time
import json
from typing import Callable, Any, Awaitable, Dict, Tuple

from . import glitter
from .base import StateContainerBase, make_callback_decorator
from ..state import Trigger
from ..store import *
from .. import utils
from .. import secret

on_action, action_listeners = make_callback_decorator()

class Reducer(StateContainerBase):
    SYNC_THROTTLE_S = 1
    SYNC_INTERVAL_S = 3

    def __init__(self, process_name: str):
        super().__init__(process_name)

        self.action_socket: Socket = self.glitter_ctx.socket(zmq.REP)
        self.event_socket: Socket = self.glitter_ctx.socket(zmq.PUB)

        self.action_socket.setsockopt(zmq.RCVTIMEO, glitter.CALL_TIMEOUT_MS)
        self.action_socket.setsockopt(zmq.SNDTIMEO, glitter.CALL_TIMEOUT_MS)
        self.event_socket.setsockopt(zmq.RCVTIMEO, glitter.SYNC_TIMEOUT_MS)
        self.event_socket.setsockopt(zmq.SNDTIMEO, glitter.SYNC_TIMEOUT_MS)

        self.action_socket.bind(secret.GLITTER_ACTION_SOCKET_ADDR)
        self.event_socket.bind(secret.GLITTER_EVENT_SOCKET_ADDR)

        self.tick_updater_task: Optional[asyncio.Task[None]] = None
        self.health_check_task: Optional[asyncio.Task[None]] = None

        self.received_telemetries: Dict[str, Tuple[float, Dict[str, Any]]] = {process_name: (0, {})}

        self.last_emit_sync_time: float = 0

    async def _before_run(self) -> None:
        await super()._before_run()

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
                timestamp_ms=0,
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
            user: Optional[UserStore] = session.execute(select(UserStore).where(UserStore.id==uid)).scalar()
            if user is None:
                return 'user not found'

            if time.time() - user.profile.timestamp_ms/1000 < UserProfileStore.UPDATE_COOLDOWN_S - 1:
                return '请求太频繁'

            allowed_profiles = UserProfileStore.PROFILE_FOR_GROUP.get(user.group, [])

            # create profile

            profile = UserProfileStore(user_id=user.id)
            for k, v in req.profile.items():
                if str(k) in allowed_profiles:
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
            user: Optional[UserStore] = session.execute(select(UserStore).where(UserStore.id==uid)).scalar()
            if user is None:
                return 'user not found'

            user.terms_agreed = True
            session.commit()
            self.state_counter += 1

        await self.emit_event(glitter.Event(glitter.EventType.UPDATE_USER, self.state_counter, uid))
        return None

    @on_action(glitter.SubmitFlagReq)
    async def on_submit_flag(self, req: glitter.SubmitFlagReq) -> Optional[str]:
        ch = self._game.challenges.chall_by_key.get(req.challenge_key, None)
        if not ch:
            return 'challenge not found'

        with self.SqlSession() as session:
            submission = SubmissionStore(
                user_id=int(req.uid),
                challenge_key=ch._store.key,
                flag=str(req.flag),
                precentage_override_or_null=(
                    GamePolicyStore.DEDUCTION_PERCENTAGE_OVERRIDE if (
                        self._game.policy.cur_policy.is_submission_deducted
                        and (ch._store.chall_metadata is None or ch._store.chall_metadata.get('score_deduction_eligible', True))
                    ) else None
                ),
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

    @on_action(glitter.SubmitFeedbackReq)
    async def on_submit_feedback(self, req: glitter.SubmitFeedbackReq) -> Optional[str]:
        uid = int(req.uid)
        ts = int(1000*time.time())

        with self.SqlSession() as session:
            user: Optional[UserStore] = session.execute(select(UserStore).where(UserStore.id == req.uid)).scalar()
            if user is None:
                return 'user not found'

            user.last_feedback_ms = ts

            feedback = FeedbackStore(
                user_id=uid,
                timestamp_ms=ts,
                challenge_key=req.challenge_key,
                content=req.feedback,
            )
            session.add(feedback)

            session.commit()
            self.state_counter += 1

        await self.emit_event(glitter.Event(glitter.EventType.UPDATE_USER, self.state_counter, uid))
        return None

    @on_action(glitter.WorkerHeartbeatReq)
    async def on_worker_heartbeat(self, req: glitter.WorkerHeartbeatReq) -> Optional[str]:
        self.received_telemetries[req.client] = (time.time(), req.telemetry)
        return None

    async def _update_tick(self, ts: Optional[int] = None) -> int: # return: when it expires
        if ts is None:
            ts = int(time.time())

        old_tick = self._game.cur_tick
        new_tick, expires = self._game.trigger.get_tick_at_time(ts)

        # DO NOT SET self._game.cur_tick = new_tick HERE because emit_event will process this and fire `on_tick_update`
        if new_tick!=old_tick:
            self.log('info', 'reducer.update_tick', f'set tick {old_tick} -> {new_tick}')

            self.state_counter += 1
            await self.emit_event(glitter.Event(glitter.EventType.TICK_UPDATE, self.state_counter, new_tick))

        return expires

    async def _tick_updater_daemon(self) -> None:
        ts = time.time()
        while True:
            expires = await self._update_tick(int(ts))
            self.log('debug', 'reducer.tick_updater_daemon', f'next tick in {"+INF" if expires==Trigger.TS_INF_S else int(expires-ts)} seconds')
            await asyncio.sleep(expires-ts+.2)
            ts = expires

    async def _health_check_daemon(self) -> None:
        while True:
            await asyncio.sleep(60)

            ws_online_uids = 0
            ws_online_clients = 0

            ts = time.time()
            for client, (last_ts, tel_data) in self.received_telemetries.items():
                if client!=self.process_name and ts-last_ts>60:
                    self.log('error', 'reducer.health_check_daemon', f'client {client} not responding in {ts-last_ts:.1f}s')
                if not tel_data.get('game_available', True):
                    self.log('error', 'reducer.health_check_daemon', f'client {client} game not available')

                ws_online_uids += tel_data.get('ws_online_uids', 0)
                ws_online_clients += tel_data.get('ws_online_clients', 0)

            st = utils.sys_status()
            if st['load_5']>st['n_cpu']*2/3:
                self.log('error', 'reducer.health_check_daemon', f'system load too high: {st["load_1"]:.2f} {st["load_5"]:.2f} {st["load_15"]:.2f}')
            if st['ram_free']/st['ram_total']<.2:
                self.log('error', 'reducer.health_check_daemon', f'free ram too low: {st["ram_free"]:.2f}G out of {st["ram_total"]:.2f}G')
            if st['disk_free']/st['disk_total']<.1:
                self.log('error', 'reducer.health_check_daemon', f'free space too low: {st["disk_free"]:.2f}G out of {st["disk_total"]:.2f}G')

            if secret.ANTICHEAT_RECEIVER_ENABLED:
                encoded = json.dumps(
                    [time.time(), {
                        'load': [st['load_1'], st['load_5'], st['load_15']],
                        'ram': [st['ram_used'], st['ram_free']],
                        'n_user': len(self._game.users.list),
                        'n_online_uid': ws_online_uids,
                        'n_online_client': ws_online_clients,
                        'n_submission': len(self._game.submissions),
                        'n_corr_submission': self._game.n_corr_submission,
                    }]
                ).encode('utf-8')

                with (secret.SYBIL_LOG_PATH/f'sys.log').open('ab') as f:
                    f.write(encoded+b'\n')

    async def handle_action(self, action: glitter.Action) -> Optional[str]:
        async def default(_self: Any, req: glitter.ActionReq) -> Optional[str]:
            return f'unknown action: {req.type}'

        listener: Callable[[Any, glitter.ActionReq], Awaitable[Optional[str]]] = action_listeners.get(type(action.req), default)

        with utils.log_slow(self.log, 'reducer.handle_action', f'handle action {action.req.type}'):
            return await listener(self, action.req)

    async def process_event(self, event: glitter.Event) -> None:
        await super().process_event(event)
        if event.type==glitter.EventType.RELOAD_TRIGGER:
            # restart tick updater deamon because next tick time may change
            if self.tick_updater_task is not None:
                self.tick_updater_task.cancel()
                self.tick_updater_task = asyncio.create_task(self._tick_updater_daemon())

    async def emit_event(self, event: glitter.Event) -> None:
        self.log('info', 'reducer.emit_event', f'emit event {event.type}')
        await self.process_event(event)

        with utils.log_slow(self.log, 'reducer.emit_event', f'emit event {event.type}'):
            await event.send(self.event_socket)

    async def emit_sync(self) -> None:
        if time.time()-self.last_emit_sync_time<=self.SYNC_THROTTLE_S:
            return
        self.last_emit_sync_time = time.time()

        #self.log('debug', 'reducer.emit_sync', f'emit sync ({self.state_counter})')
        with utils.log_slow(self.log, 'reducer.emit_sync', f'emit sync'):
            await glitter.Event(glitter.EventType.SYNC, self.state_counter, self._game.cur_tick).send(self.event_socket)

    async def _mainloop(self) -> None:
        self.log('success', 'reducer.mainloop', 'started to receive actions')
        self.tick_updater_task = asyncio.create_task(self._tick_updater_daemon())
        self.health_check_task = asyncio.create_task(self._health_check_daemon())

        while True:
            try:
                future = glitter.Action.listen(self.action_socket)
                action: Optional[glitter.Action] = await asyncio.wait_for(future, self.SYNC_INTERVAL_S)
            except asyncio.TimeoutError:
                await self.emit_sync()
                continue
            except Exception as e:
                self.log('error', 'reducer.mainloop', f'exception during action receive, will try again: {e}')
                await self.emit_sync()
                await asyncio.sleep(self.SYNC_INTERVAL_S)
                continue

            if action is None:
                continue

            if isinstance(action.req, glitter.WorkerHelloReq):
                self.log('debug', 'reducer.mainloop', f'got worker hello from {action.req.client}')
            elif isinstance(action.req, glitter.WorkerHeartbeatReq):
                pass
            else:
                self.log('info', 'reducer.mainloop', f'got action {action.req.type} from {action.req.client}')

            old_counter = self.state_counter

            try:
                if action is None:
                    err: Optional[str] = 'malformed glitter packet'
                else:
                    err = await self.handle_action(action)

                if err is not None and action.req.type!='SubmitFlagReq':
                    self.log('warning', 'reducer.handle_action', f'error for action {action.req.type}: {err}')
            except Exception as e:
                self.log('critical', 'reducer.handle_action', f'exception, will report as internal error: {utils.get_traceback(e)}')
                err = '内部错误，已记录日志'

            if self.state_counter!=old_counter:
                self.log('debug', 'reducer.mainloop', f'state counter {old_counter} -> {self.state_counter}')
            assert self.state_counter-old_counter in [0, 1], 'action handler incremented state counter more than once'

            if action is not None:
                with utils.log_slow(self.log, 'reducer.mainloop', f'reply to action {action.req.type}'):
                    await action.reply(glitter.ActionRep(error_msg=err, state_counter=self.state_counter),self.action_socket)

            if not isinstance(action.req, glitter.WorkerHeartbeatReq):
                await self.emit_sync()