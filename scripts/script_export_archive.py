import asyncio
import datetime
from pathlib import Path
from typing import List, Dict, Any
import json
import shutil
import csv

from src.logic.worker import Worker
from src.state import Game, Challenge, ScoreBoard, FirstBloodBoard, Announcements
from src import utils
from src import secret

EXPORT_PATH = Path('../exported-archive')
if EXPORT_PATH.is_dir():
    shutil.rmtree(EXPORT_PATH)
EXPORT_PATH.mkdir()

UID_FOR_DYN_ATTACHMENT = 2

with open('/scripts/probid_mapping.json') as f:
    PROBID_MAPPING: Dict[str, str] = json.load(f)

def gen_md_table(headers: List[str], rows: List[List[str]]) -> str:
    ret = []
    ret.append(f'| {" | ".join(headers)} |')
    ret.append(f'| {" | ".join(["---"]*len(headers))} |')
    for row in rows:
        ret.append(f'| {" | ".join([str(x) for x in row])} |')
    return '\n'.join(ret)

def rm_common_header(rows: List[List[str]], n: int) -> None:
    if not rows:
        return

    last_r = rows[0][:]
    for r in rows[1:]:
        new_r = r[:]
        for i in range(n):
            if r[i]==last_r[i]:
                r[i] = ''
        last_r = new_r

def export_problemset(game: Game) -> None:
    HEADERS = ['分类', '#', '官方题解和源码', '题目标题', 'Flag', '分值', '校内通过', '总通过']

    d = []

    rows = []
    for ch in game.challenges.list:
        for flag in ch.flags:
            n_passed = {
                'pku_1': 0,
                'pku_2': 0,
                'other_1': 0,
                'other_2': 0,
            }

            for u in flag.passed_users:
                sub = u.passed_flags[flag]
                cat = '2' if sub._store.precentage_override_or_null is not None else '1'
                grp = 'pku' if u._store.group == 'pku' else 'other'
                n_passed[f'{grp}_{cat}'] += 1

            rows.append([
                ch._store.category,
                ch._store.key,
                f'[→ {PROBID_MAPPING[ch._store.key]}](../official_writeup/{PROBID_MAPPING[ch._store.key]}/)',
                ch._store.title,
                flag.name or '/',
                flag.base_score,
                f'{n_passed["pku_1"]}+{n_passed["pku_2"]}',
                f'{n_passed["pku_1"]+n_passed["other_1"]}+{n_passed["pku_2"]+n_passed["other_2"]}',
            ])

    rm_common_header(rows, 4)

    d.append('# 题目列表')
    d.append(gen_md_table(HEADERS, rows))
    d.append('“分值” 表示题目原始分值，实际分值取决于校内第一阶段通过人数。')
    d.append('“校内通过” 和 “总通过” 人数的两个部分分别表示第一阶段和第二阶段的通过人数。')

    for ch in game.challenges.list:
        d.append(f'## [{ch._store.category}] {ch._store.title}')
        d.append(f'**[【→ 官方题解和源码】](../official_writeup/{PROBID_MAPPING[ch._store.key]}/)**')
        d.append(ch._store.desc_template)

    with (EXPORT_PATH / 'problemset' / 'README.md').open('w', encoding='utf-8') as f:
        f.write('\n\n'.join(d))

def copy_attachment(act: Dict[str, Any], p: Path) -> str:
    p = p / 'attachment'
    p.mkdir(exist_ok=True)

    fn = act['filename']

    if act['type'] == 'attachment':
        shutil.copyfile(secret.ATTACHMENT_PATH / act['file_path'], p / fn)
    elif act['type'] == 'dyn_attachment':
        shutil.copyfile(secret.ATTACHMENT_PATH / act['module_path'] / '_cache' / f'{UID_FOR_DYN_ATTACHMENT}.bin', p / fn)

    return fn

def export_official_writeup(ch: Challenge, p: Path) -> None:
    p.mkdir()

    d = []

    d.append(f'# [{ch._store.category}] {ch._store.title}')
    d.append(
        f'- 命题人：{ch._store.chall_metadata.get("author", "???")}' +
        '\n'.join([
            f'- {f.name or "题目分值"}：{f.base_score} 分'
            for f in ch.flags
        ])
    )

    d.append('## 题目描述')
    d.append(ch._store.desc_template)

    for act in ch._store.actions:
        if act['type'] in ['attachment', 'dyn_attachment']:
            fn = copy_attachment(act, p)
            if act['name'] is None:
                d.append(f'**[【隐藏附件：{fn}】](attachment/{fn})**')
            else:
                d.append(f'**[【附件：下载{act["name"]}（{fn}）】](attachment/{fn})**')
        elif act['type'] in ['webpage', 'webdocker']:
            d.append(f'**【网页链接：访问{act["name"]}】**')
        elif act['type']=='terminal':
            d.append(f'**【终端交互：连接到{act["name"]}】**')
        else:
            assert False, act['type']

    d.append('## 预期解法')
    d.append('TODO: 出题人题解，后面可以按需增加更多的二级标题')

    with (p / 'README.md').open('w', encoding='utf-8') as f:
        f.write('\n\n'.join(d))

def export_ranking_list(game: Game):
    d = []

    d.append('# 排行榜')

    d.append('\n'.join(
        f'- [{b.name}]({key}.csv)'
        for key, b in game.boards.items()
    ))

    d.append('分数排行截止到前100名。只有“北京大学”组别的校内选手参与评奖。')
    d.append(f'排行榜存档时间为 {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}，选手昵称可能有变化。')

    with (EXPORT_PATH / 'ranking' / 'README.md').open('w', encoding='utf-8') as f:
        f.write('\n\n'.join(d))

def format_badge(badges: List[str]) -> str:
    ret = []
    if 'girl' in badges:
        ret.append('女生')
    if 'rookie' in badges:
        ret.append('新生')

    if ret:
        return f'（{"，".join(ret)}）'
    else:
        return ''

def format_ts(ts: int) -> str:
    return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

def export_ranking_score(b: ScoreBoard, p: Path) -> None:
    li: List[Dict[str, Any]] = b.get_rendered(False)['list']

    with p.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['名次', '昵称', '组别', '总分', '最后提交时间'])

        for i, row in enumerate(li):
            w.writerow([
                i + 1,
                row['nickname'],
                row['group_disp'] + format_badge(row['badges']),
                row['score'],
                format_ts(row['last_succ_submission_ts']),
            ])

def export_ranking_firstblood(b: FirstBloodBoard, p: Path) -> None:
    li: List[Dict[str, Any]] = b.get_rendered(False)['list']

    with p.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['题目', 'Flag', '一血获得者', '组别', '提交时间'])

        for row_c in li:
            for row_f in row_c['flags']:
                w.writerow([
                    row_c['title'],
                    row_f['flag_name'] or '/',
                    row_f['nickname'],
                    row_f['group_disp'] + format_badge(row_f['badges']),
                    format_ts(row_c['timestamp']),
                ])

def export_announcements(ann: Announcements):
    d = []

    d.append('# 公告')

    for a in ann.list:
        d.append(f'## {a.title}')
        d.append(f'（发布时间：{format_ts(a.timestamp_s)}）' )
        d.append(a._store.content_template)

    with (EXPORT_PATH / 'announcements' / 'README.md').open('w', encoding='utf-8') as f:
        f.write('\n\n'.join(d))

def export_game(game: Game):
    export_problemset(game)

    for ch in game.challenges.list:
        export_official_writeup(ch, EXPORT_PATH / 'official_writeup' / PROBID_MAPPING[ch._store.key])

    (EXPORT_PATH / 'ranking').mkdir()
    export_ranking_list(game)

    for key, b in game.boards.items():
        p = EXPORT_PATH / 'ranking' / f'{key}.md'
        if isinstance(b, ScoreBoard):
            export_ranking_score(b, p)
        elif isinstance(b, FirstBloodBoard):
            export_ranking_firstblood(b, p)
        else:
            assert False, f'unknown type for board {key}: {type(b)}'

    export_announcements(game.announcements)

if __name__=='__main__':
    utils.fix_zmq_asyncio_windows()

    worker = Worker('worker-test')
    asyncio.run(worker._before_run())

    export_game(worker.game)