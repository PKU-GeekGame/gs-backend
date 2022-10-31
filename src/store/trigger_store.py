from sqlalchemy import Column, Integer, String, BigInteger

from . import Table

class TriggerStore(Table):
    __tablename__ = 'trigger'

    tick: int = Column(Integer, nullable=False, unique=True)
    timestamp_s: int = Column(BigInteger, nullable=False, unique=True)
    name: str = Column(String(64), nullable=False)

