import asyncio
from pathlib import Path
import sys
import json
import shutil
from typing import List

sys.path.append(str(Path('.').resolve()))

from src.logic.worker import Worker
from src.state import User, Challenge
from src.store import ChallengeStore
from src import utils
from src import secret

WRITEUP_UIDS = [1]

EXPORT_PATH = Path('../players-writeup')
if EXPORT_PATH.is_dir():
    shutil.rmtree(EXPORT_PATH)
EXPORT_PATH.mkdir()

def md_escape(s: str) -> str:
    for c in r'\`*_{}[]<>()#+-.!|':
        s = s.replace(c, f'\\{c}')
    return s

def gen_md_table(headers: List[str], rows: List[List[str]]) -> str:
    ret = []
    ret.append(f'| {" | ".join(headers)} |')
    ret.append(f'| {" | ".join(["---"]*len(headers))} |')
    for row in rows:
        ret.append(f'| {" | ".join([str(x) for x in row])} |')
    return '\n'.join(ret)

def chall_status(u: User, ch: Challenge) -> str:
    if u in ch.passed_users:
        return 'P'
    elif u in ch.touched_users:
        fs = len([1 for f in ch.flags if u in f.passed_users])
        return str(fs)
    else:
        return '-'

if __name__=='__main__':
    utils.fix_zmq_asyncio_windows()

    worker = Worker('worker-test')
    asyncio.run(worker._before_run())

    ch_list = {cat: [] for cat in ChallengeStore.CAT_COLORS}
    for ch in worker.game.challenges.list:
        ch_list[ch._store.category].append(ch)

    d = []

    d.append('# 选手题解')

    HEADERS = ['选手', '公开理由', '总分', '授权', *ch_list.keys()]

    rows = []
    for uid in WRITEUP_UIDS:
        u = worker.game.users.user_by_id[uid]

        with (secret.WRITEUP_PATH / str(u._store.id) / 'metadata.json').open() as f:
            metadata = json.load(f)

        assert metadata['publish'].strip().lower()!='always-no'

        rows.append([
            f'[{md_escape(u._store.profile.nickname_or_null)}]({u._store.id}/)',
            '选手要求' if metadata['publish'].strip().lower()=='always-yes' else '',
            u.tot_score,
            metadata['rights'],
            *[f'`{"".join(chall_status(u, ch) for ch in chs)}`' for chs in ch_list.values()]
        ])

        (EXPORT_PATH / str(u._store.id)).mkdir()
        shutil.copyfile(
            secret.WRITEUP_PATH / str(u._store.id) / metadata['filename'],
            (EXPORT_PATH / str(u._store.id) / metadata['filename']).with_name('writeup' + Path(metadata['filename']).suffix)
        )

    rows.sort(key=lambda r: r[2], reverse=True)

    d.append(gen_md_table(HEADERS, rows))

    d.append('**关于授权方式：**')
    d.append(
        '- 标为 “All-Rights-Reserved” 的题解作者保留所有权利，不允许读者转载或改编相关内容。\n'
        '- 标为 “CC-BY-NC” 的题解按照 [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) 授权，允许读者在注明出处的情况下非商业使用相关内容。\n'
        '- 标为 “CC0” 的题解按照 [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) 授权，允许读者任意使用相关内容。'
    )

    d.append('**关于通过题目列表：**')
    d.append('`P` 表示通过此题，`-` 表示未通过此题的任何 Flag，数字表示通过了部分 Flag。')

    with (EXPORT_PATH / 'README.md').open('w') as f:
        f.write('\n\n'.join(d))