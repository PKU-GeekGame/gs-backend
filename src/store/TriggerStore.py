from sqlalchemy import Column, Integer, String, BigInteger

from . import Table

class TriggerStore(Table):
    __tablename__ = 'trigger'

    timing = Column(Integer, unique=True, nullable=False)
    timestamp_s = Column(BigInteger, nullable=False)
    name = Column(String(64), nullable=False)

