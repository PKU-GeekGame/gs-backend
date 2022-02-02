from sqlalchemy import Column, Integer, Boolean, String, Text, JSON

from . import Table

class ChallengeStore(Table):
    __tablename__ = 'challenge'

    effective_after = Column(Integer, nullable=False)

    title = Column(String(64), nullable=False)
    category = Column(String(32), nullable=False)
    sorting_index = Column(Integer, nullable=False)
    desc_template = Column(Text, nullable=False)

    actions = Column(JSON, nullable=False)
    flags = Column(JSON, nullable=False)