from __future__ import annotations
from sqlalchemy import Column, Integer, Boolean

from . import Table

class GamePolicyStore(Table):
    __tablename__ = 'game_policy'

    effective_after: int = Column(Integer, unique=True, nullable=False)

    can_view_problem: bool = Column(Boolean, nullable=False)
    can_submit_flag: bool = Column(Boolean, nullable=False)
    can_submit_writeup: bool = Column(Boolean, nullable=False)
    is_submission_deducted: bool = Column(Boolean, nullable=False)

    DEDUCTION_PERCENTAGE_OVERRIDE = 35

    @classmethod
    def fallback_policy(cls) -> GamePolicyStore:
        return cls(
            effective_after=0,
            can_view_problem=False,
            can_submit_flag=False,
            can_submit_writeup=False,
            is_submission_deducted=False,
        )

    @property
    def show_problems_to_guest(self) -> bool:
        # show problems list to guest during the game to promote participation
        return self.can_view_problem and self.can_submit_flag