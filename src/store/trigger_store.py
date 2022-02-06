from sqlalchemy import Column, Integer, String, BigInteger

from . import Table

class TriggerStore(Table):
    __tablename__ = 'trigger'

    tick = Column(Integer, nullable=False, unique=True)
    timestamp_s = Column(BigInteger, nullable=False, unique=True)
    name = Column(String(64), nullable=False)

