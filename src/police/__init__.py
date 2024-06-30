import asyncio
import json

from ..logic import Worker
from ..state import Submission, User
from .. import utils

TIME_MAX = 1e50
MAX_ROWS = 7

async def check_submission(sub: Submission, worker: Worker) -> None:
    if sub.matched_flag is not None or sub.duplicate_submission: # correct answer, no need to check
        return

    if worker.game is None:
        worker.log('error', 'police.check_submission', f'game is dirty now, cannot check S#{sub._store.id}')
        return

    ch = sub.challenge
    submitter = sub.user

    if ch is None: # maybe challenge key is changed
        return

    origin_users = []
    accepted_origin_users = {}

    for f in ch.flags:
        if f.type=='static': # cannot check static flag
            continue

        for u in worker.game.users.list:
            if f.validate_flag(u, sub._store.flag):
                origin_users.append(u)
                if f in u.passed_flags.keys():
                    accepted_origin_users[u] = u.passed_flags[f]

    if not origin_users: # genuine wrong submission
        worker.log('debug', 'police.check_submission', f'S#{sub._store.id} seems fine')
        return

    origin_users.sort(key=lambda u: (
        (accepted_origin_users[u]._store.timestamp_ms if u in accepted_origin_users else TIME_MAX), # first submitted user first
        0 if u.tot_score>0 else 1, # participated users first
        u._store.id, # old users first
    ))

    def describe_origin(u: User) -> str:
        sub = accepted_origin_users.get(u, None)
        if sub:
            return f'({utils.format_timestamp(sub._store.timestamp_ms/1000)})'
        elif u.tot_score>0:
            return '(does not pass)'
        else:
            return '(empty user)'

    report_text = (
        f'S#{sub._store.id} (U#{submitter._store.id} {submitter._store.login_key} ch={ch._store.key}) matches {len(origin_users)} origin users:\n'
        + '\n'.join(
            f'- U#{u._store.id} {u._store.login_key} {describe_origin(u)}'
            for u in origin_users
        )
    )

    msg_text = (
        f'S#{sub._store.id} (U#{submitter._store.id} {submitter._store.login_key} ch={ch._store.key}) matches {len(origin_users)} origin users:\n'
        + '\n'.join(
            f'- U#{u._store.id} {u._store.login_key} {describe_origin(u)}'
            for u in origin_users[:MAX_ROWS]
        )
        + (f'\n(showing first {MAX_ROWS})' if MAX_ROWS<=len(origin_users) else '')
    )

    worker.log('success', 'police.check_submission', report_text)
    await worker.push_message(f'[POLICE] {msg_text}', f'police:{submitter._store.id}')

async def run_forever() -> None:
    worker = Worker('police', receiving_messages=True)
    await worker._before_run()

    async def task() -> None:
        await worker._mainloop()
        worker.log('critical', 'police.run_police_forever', 'worker mainloop stopped')

    asyncio.create_task(task())

    message_id = worker.next_message_id
    while True:
        async with worker.message_cond:
            await worker.message_cond.wait_for(lambda: message_id<worker.next_message_id)

            while message_id<worker.next_message_id:
                msg = worker.local_messages.get(message_id, None)
                message_id += 1

                if msg is None:
                    worker.log('error', 'police.police_process', f'lost local message {message_id}, maybe we stucked for a long time?')
                else:
                    if msg.get('type', None)=='new_submission':
                        sub: Submission = msg['submission']
                        with utils.log_slow(worker.log, 'police.police_process', f'check submission {sub._store.id}', 1):
                            await check_submission(sub, worker)
                    elif msg.get('type', None)=='push':
                        payload = msg['payload']
                        await worker.push_message(f'[PUSH] {json.dumps(payload, indent=1, ensure_ascii=False)}', None)

def police_process() -> None:
    asyncio.run(run_forever())