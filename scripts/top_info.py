import asyncio
from pathlib import Path
import sys

sys.path.append(str(Path('.').resolve()))

from src.logic.worker import Worker
from src.state import ScoreBoard, FirstBloodBoard, User
from src import utils

N_TOP = 50
N_THRESHOLD = 30

PKU_HEADERS = [
    'UID', 'NICKNAME',
    'NAME', 'STU_ID', 'DEPT', 'TYPE',
    'TEL', 'QQ',
]

def pku_info(u: User) -> list[str]:
    prop = u._store.login_properties
    prof = u._store.profile

    assert prop['type'] == 'iaaa'
    assert '\t' not in prof.nickname_or_null

    return [
        str(u._store.id), prof.nickname_or_null,
        prop['info']['name'], prop['info']['identityId'], prop['info']['dept'], prop['info']['detailType'],
        prof.tel_or_null,
        prof.qq_or_null,
    ]

THU_HEADERS = [
    'UID', 'NICKNAME',
    'TYPE',
    'STU_ID', 'EMAIL', 'QQ',
]

def thu_info(u: User) -> list[str]:
    prop = u._store.login_properties
    prof = u._store.profile

    assert prop['type'] == 'carsi'
    assert '\t' not in prof.nickname_or_null

    return [
        str(u._store.id), prof.nickname_or_null,
        prop['info']['usertype'],
        prof.stuid_or_null, prof.email_or_null, prof.qq_or_null,
    ]

OTHER_HEADERS = [
    'UID', 'NICKNAME', 'QQ',
]

def other_info(u: User) -> list[str]:
    prof = u._store.profile

    assert '\t' not in prof.nickname_or_null

    return [
        str(u._store.id), prof.nickname_or_null, prof.qq_or_null,
    ]

if __name__=='__main__':
    utils.fix_zmq_asyncio_windows()

    worker = Worker('worker-test')
    asyncio.run(worker._before_run())

    score_threshold = 0

    for schoolname, b_sfx, headers, info_getter in [
        ('北京大学', 'pku', PKU_HEADERS, pku_info),
        ('清华大学', 'thu', THU_HEADERS, thu_info),
    ]:
        b = worker.game.boards[f'score_{b_sfx}']
        assert isinstance(b, ScoreBoard)
        score_threshold = max(score_threshold, b.board[N_THRESHOLD-1][1])

        print(f'【{schoolname} 成绩】')
        print('RANK', 'SCORE', *headers, sep='\t')

        rookies = []
        for ind, (u, score) in enumerate(b.board[:N_TOP]):
            row = [str(ind+1), str(score)] + info_getter(u)
            print(*row, sep='\t')

            badges =  u._store.badges()
            if 'rookie' in badges and len(rookies)<3:
                rookies.append(row)

        print(f'【{schoolname} 新生奖】')
        print('RANK', 'SCORE', *headers, sep='\t')
        for row in rookies:
            print(*row, sep='\t')

        b = worker.game.boards[f'first_{b_sfx}']
        assert isinstance(b, FirstBloodBoard)

        print(f'【{schoolname} 解题先锋奖】')
        print('CATEGORY', 'CHALLENGE', *headers, sep='\t')

        for ch, sub in sorted(b.chall_board.items(), key=lambda e: e[0]._store.sorting_index):
            if not ch._store.chall_metadata.get('first_blood_award_eligible', False):
                continue

            u = sub.user

            row = [ch._store.category, ch._store.title] + info_getter(u)
            print(*row, sep='\t')

    b = worker.game.boards['score_other']
    assert isinstance(b, ScoreBoard)

    print('【校外成绩证明】')
    print(*['RANK', 'SCORE', 'UID', 'NICKNAME', 'QQ'], sep='\t')
    for ind, (u, score) in enumerate(b.board):
        if score<score_threshold:
            break

        assert u._store.group == 'other'

        print(ind+1, score, *other_info(u), sep='\t')