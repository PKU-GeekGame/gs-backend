from sqlalchemy import Column, Integer, Boolean

from . import Table

class GamePolicyStore(Table):
    __tablename__ = 'game_policy'

    effective_after = Column(Integer, unique=True, nullable=False)

    can_view_problem = Column(Boolean, nullable=False)
    can_submit_flag = Column(Boolean, nullable=False)
    can_submit_writeup = Column(Boolean, nullable=False)


