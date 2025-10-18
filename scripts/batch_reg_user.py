import asyncio
from pathlib import Path
import sys

sys.path.append(str(Path('.').resolve()))

from src.logic.worker import Worker
from src.store import UserStore
from src.logic import glitter
from src import utils

async def main():
    worker = Worker('worker-test')
    await worker._before_run()
    _t = asyncio.create_task(worker._mainloop())

    group_mapping = {
        **{k: k for k, v in UserStore.GROUPS.items()},
        **{v: k for k, v in UserStore.GROUPS.items()},
    }

    userlist = []
    with open(sys.argv[1], encoding='utf-8') as f:
        for line in f.read().splitlines():
            if not line.strip():
                continue
            identity, password, group = line.split('\t')
            group = group_mapping[group.strip()]
            identity = identity.strip()
            password = password.strip()
            userlist.append((group, identity, password))

    for group, identity, password in userlist:
        login_key = f'email:{identity}'
        if login_key in worker._game.users.user_by_login_key:
            user = worker._game.users.user_by_login_key[login_key]
        else:
            rep = await worker.perform_action(glitter.RegUserReq(
                client='script',
                login_key=login_key,
                login_properties={'type': 'user', 'identity': identity, 'password': password},
                group=group,
            ))

            if rep.error_msg is None:
                user = worker.game.users.user_by_login_key.get(login_key)
                assert user is not None, 'user should be created'
            else:
                raise RuntimeError(f'注册账户失败：{rep.error_msg}')
        print(f'{UserStore.GROUPS[group]},{identity},{password},{user._store.auth_token}')

if __name__=='__main__':
    utils.fix_zmq_asyncio_windows()
    asyncio.run(main())
