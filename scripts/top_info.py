import asyncio
from pathlib import Path
import sys

sys.path.append(str(Path('.').resolve()))

from src.logic.worker import Worker
from src.state import ScoreBoard, FirstBloodBoard
from src import utils

N_TOP = 50
N_THRESHOLD = 30

if __name__=='__main__':
    utils.fix_zmq_asyncio_windows()

    worker = Worker('worker-test')
    asyncio.run(worker._before_run())

    b = worker.game.boards['score_pku']
    assert isinstance(b, ScoreBoard)
    score_threshold = b.board[N_THRESHOLD-1][1]

    print('【校内成绩】')
    print(*['RANK', 'SCORE', 'UID', 'NICKNAME', 'NAME', 'STU_ID', 'DEPT', 'TYPE', 'TEL', 'QQ'], sep='\t')

    rookies = []
    for ind, (u, score) in enumerate(b.board[:N_TOP]):
        prop = u._store.login_properties
        prof = u._store.profile

        assert prop['type']=='iaaa'
        assert '\t' not in prof.nickname_or_null

        row = [ind+1, score, u._store.id, prof.nickname_or_null, prop["info"]["name"], prop["info"]["identityId"], prop["info"]["dept"], prop["info"]["detailType"], prof.tel_or_null, prof.qq_or_null]
        print(*row, sep='\t')

        badges =  u._store.badges()
        if 'rookie' in badges and len(rookies)<3:
            rookies.append(row)

    print('【新生奖】')
    print(*['RANK', 'SCORE', 'UID', 'NICKNAME', 'NAME', 'STU_ID', 'DEPT', 'TYPE', 'TEL', 'QQ'], sep='\t')
    for row in rookies:
        print(*row, sep='\t')

    b = worker.game.boards['first_pku']
    assert isinstance(b, FirstBloodBoard)

    print('【解题先锋奖】')
    print(*['CATEGORY', 'CHALLENGE', 'UID', 'NICKNAME', 'NAME', 'STU_ID', 'DEPT', 'TYPE', 'TEL', 'QQ'], sep='\t')

    for ch, sub in sorted(b.chall_board.items(), key=lambda e: e[0]._store.sorting_index):
        if not ch._store.chall_metadata.get('first_blood_award_eligible', False):
            continue

        u = sub.user
        prop = u._store.login_properties
        prof = u._store.profile

        assert prop['type']=='iaaa'
        assert '\t' not in prof.nickname_or_null

        row = [ch._store.category, ch._store.title, u._store.id, u._store.profile.nickname_or_null, prop["info"]["name"], prop["info"]["identityId"], prop["info"]["dept"], prop["info"]["detailType"], prof.tel_or_null, prof.qq_or_null,]
        print(*row, sep='\t')

    b = worker.game.boards['score_all']
    assert isinstance(b, ScoreBoard)

    print('【校外成绩证明】')
    print(*['RANK', 'SCORE', 'UID', 'NICKNAME', 'QQ'], sep='\t')
    for ind, (u, score) in enumerate(b.board):
        if u._store.group=='pku':
            continue
        if score<score_threshold:
            break

        prof = u._store.profile
        assert '\t' not in prof.nickname_or_null

        print(ind+1, score, u._store.id, prof.nickname_or_null, prof.qq_or_null, sep='\t')