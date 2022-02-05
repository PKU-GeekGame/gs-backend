from __future__ import annotations
from enum import Enum, unique
import json
from typing import TYPE_CHECKING, Dict, Any, Optional, Union, Literal, List

from .. import utils

PROTOCOL_VER = 'alpha.v1'

@unique
class ActionType(Enum):
    WORKER_HELLO = 'worker_hello'

    REG_USER = 'reg_user'
    UPDATE_PROFILE = 'update_profile'
    SUBMIT_FLAG = 'submit_flag'

@unique
class EventType(Enum):
    SYNC = b'\x01'

    RELOAD_GAME_POLICY = b'\x11'
    RELOAD_TRIGGER = b'\x12'
    RELOAD_SUBMISSION = b'\x13'

    UPDATE_ANNOUNCEMENT = b'\x21'
    UPDATE_CHALLENGE = b'\x22'
    UPDATE_USER = b'\x23'

    NEW_SUBMISSION = b'\x31'
    TICK_UPDATE = b'\x32'

if TYPE_CHECKING:
    from zmq.asyncio import Socket
    from typing_extensions import TypedDict

    class ActionReq(TypedDict):
        ssrf_token: str
    class ActionRep(TypedDict):
        error_msg: Optional[str]
        state_counter: int

    class WorkerHelloReq(ActionReq):
        type: Literal[ActionType.WORKER_HELLO]
        protocol_ver: str

    class RegUserReq(ActionReq):
        type: Literal[ActionType.REG_USER]
        login_type: str
        login_identity: str
        login_peoperties: Any
        group: str

    class UpdateProfileReq(ActionReq):
        type: Literal[ActionType.UPDATE_PROFILE]
        uid: int
        profile: Dict[str, str]

    class SubmitFlagReq(ActionReq):
        type: Literal[ActionType.SUBMIT_FLAG]
        uid: int
        challenge_id: int
        flag: str

    SomeActionReq = Union[WorkerHelloReq, RegUserReq, UpdateProfileReq, SubmitFlagReq]

CALL_TIMEOUT_MS = 5000

class Action:
    def __init__(self, req: SomeActionReq):
        self.req: SomeActionReq = req
        assert 'type' in self.req

    async def _send_req(self, sock: Socket) -> None:
        sent_req = {
            **self.req,
            'type': self.req['type'].value,
        }
        await sock.send_multipart([json.dumps(sent_req).encode('utf-8')]) # type: ignore
    @staticmethod
    async def _recv_rep(sock: Socket) -> ActionRep:
        parts = await sock.recv_multipart() # type: ignore
        assert len(parts)==1
        rep: ActionRep = json.loads(parts[0].decode('utf-8'))
        assert 'error_msg' in rep and 'state_counter' in rep
        return rep

    # client

    async def call(self, sock: Socket) -> ActionRep:
        await self._send_req(sock)
        return await self._recv_rep(sock)

    # server

    @classmethod
    async def listen(cls, sock: Socket) -> Optional[Action]:
        pkt = await sock.recv_multipart() # type: ignore
        try:
            assert len(pkt)==1
            req_b = pkt[0]
            data = json.loads(req_b.decode('utf-8'))
            assert 'ssrf_token' in data and 'type' in data
            data['type'] = ActionType(data['type'])
            return cls(data)
        except Exception as e:
            print(utils.get_traceback(e))
            sock.send_multipart([json.dumps({ # type: ignore
                'error_msg': 'malformed packet',
                'state_counter': -1,
            }).encode('utf-8')])
            return None

    async def reply(self, rep: ActionRep, sock: Socket) -> None:
        await sock.send_multipart([json.dumps(rep).encode('utf-8')]) # type: ignore

SYNC_INTERVAL_S = 3
SYNC_TIMEOUT_MS = 7000

class Event:
    def __init__(self, type: EventType, state_counter: int, data: int):
        self.type: EventType = type
        self.state_counter: int = state_counter
        self.data: int = data

    # client

    @classmethod
    async def next(cls, sock: Socket) -> Event:
        type, ts, id = await sock.recv_multipart() # type: ignore
        type = EventType(type)
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
        await sock.send_multipart(data) # type: ignore