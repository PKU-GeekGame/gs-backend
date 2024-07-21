from __future__ import annotations
from enum import Enum, unique
import json
from dataclasses import dataclass
from zmq.asyncio import Socket
import pickle
import asyncio
from typing import Dict, Any, Optional, List

from .. import utils
from .. import secret

PROTOCOL_VER = 'glitter.alpha.v2'

@unique
class EventType(Enum):
    SYNC = b'\x01'

    RELOAD_GAME_POLICY = b'\x11'
    RELOAD_TRIGGER = b'\x12'

    UPDATE_ANNOUNCEMENT = b'\x21'
    UPDATE_CHALLENGE = b'\x22'
    UPDATE_USER = b'\x23'
    UPDATE_SUBMISSION = b'\x24'

    NEW_SUBMISSION = b'\x31'
    TICK_UPDATE = b'\x32'

@dataclass
class ActionReq:
    client: str
    @property
    def type(self) -> str:
        return type(self).__name__

@dataclass
class WorkerHeartbeatReq(ActionReq):
    telemetry: Dict[str, Any]

@dataclass
class WorkerHelloReq(ActionReq):
    protocol_ver: str

@dataclass
class RegUserReq(ActionReq):
    login_key: str
    login_properties: Dict[str, Any]
    group: str

@dataclass
class UpdateProfileReq(ActionReq):
    uid: int
    profile: Dict[str, str]

@dataclass
class AgreeTermReq(ActionReq):
    uid: int

@dataclass
class SubmitFlagReq(ActionReq):
    uid: int
    challenge_key: str
    flag: str

@dataclass
class SubmitFeedbackReq(ActionReq):
    uid: int
    challenge_key: str
    feedback: str

@dataclass
class ActionRep:
    error_msg: Optional[str]
    state_counter: int

CALL_TIMEOUT_MS = 5000

class Action:
    _lock: Optional[asyncio.Lock] = None
    def __init__(self, req: ActionReq):
        self.req: ActionReq = req

    async def _send_req(self, sock: Socket) -> None:
        await sock.send_multipart([secret.GLITTER_SSRF_TOKEN.encode(), pickle.dumps(self.req)])
    @staticmethod
    async def _recv_rep(sock: Socket) -> ActionRep:
        parts = await sock.recv_multipart()
        assert len(parts)==1, 'malformed action rep packet: should contain one part'
        rep = pickle.loads(parts[0])
        assert isinstance(rep, ActionRep)
        return rep

    # client

    async def call(self, sock: Socket) -> ActionRep:
        if Action._lock is None:
            Action._lock = asyncio.Lock()

        async with Action._lock:
            await self._send_req(sock)
            ret = await self._recv_rep(sock)
            return ret

    # server

    @classmethod
    async def listen(cls, sock: Socket) -> Optional[Action]:
        pkt = await sock.recv_multipart()
        try:
            assert len(pkt)==2, 'action req packet should contain one part'
            assert pkt[0]==secret.GLITTER_SSRF_TOKEN.encode(), 'invalid ssrf token'
            data = pickle.loads(pkt[1])
            assert isinstance(data, ActionReq), 'malformed action req packet body'
            return cls(data)
        except Exception as e:
            print(utils.get_traceback(e))
            await sock.send_multipart([json.dumps({
                'error_msg': 'malformed packet',
                'state_counter': -1,
            }).encode('utf-8')])
            return None

    @staticmethod
    async def reply(rep: ActionRep, sock: Socket) -> None:
        await sock.send_multipart([pickle.dumps(rep)])


SYNC_TIMEOUT_MS = 7000

class Event:
    def __init__(self, type: EventType, state_counter: int, data: int):
        self.type: EventType = type
        self.state_counter: int = state_counter
        self.data: int = data

    # client

    @classmethod
    async def next(cls, sock: Socket) -> Event:
        type_str, ts, id = await sock.recv_multipart()
        type = EventType(type_str)
        cnt = int(ts.decode('utf-8'))
        data = int(id.decode('utf-8'))
        return cls(type=type, state_counter=cnt, data=data)

    # server

    async def send(self, sock: Socket) -> None:
        data: List[bytes] = [
            self.type.value,
            str(self.state_counter).encode('utf-8'),
            str(self.data).encode('utf-8'),
        ]
        await sock.send_multipart(data)