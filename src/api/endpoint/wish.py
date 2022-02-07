from sanic import Blueprint, Request
from typing import Optional, Dict, Any

from ..wish import wish_endpoint
from ...state import User
from ...logic import Worker
from ...store import UserProfileStore

bp = Blueprint('endpoint', url_prefix='/wish')

@wish_endpoint(bp, '/game_info')
async def game_info(_req: Request, _worker: Worker, user: Optional[User]) -> Dict[str, Any]:
    return {
        'user': None if user is None else {
            'id': user._store.id,
            'group': user._store.group,
            'token': user._store.token,
            'profile': {
                field: (
                    getattr(user._store.profile, f'{field}_or_null') or ''
                ) for field in UserProfileStore.PROFILE_FOR_GROUP.get(user._store.group, [])
            },
        },
        'feature': {
            'push': True,
            'game': user is not None and user.check_play_game() is not None,
        },
    }