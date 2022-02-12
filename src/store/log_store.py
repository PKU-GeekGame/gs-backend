from sqlalchemy import Column, BigInteger, String, Text
import time

from . import Table

class LogStore(Table):
    __tablename__ = 'log'

    timestamp_ms = Column(BigInteger, nullable=False, default=lambda: int(1000*time.time()))
    level = Column(String(32), nullable=False)
    process = Column(String(32), nullable=False)
    module = Column(String(32), nullable=False)
    message = Column(Text, nullable=False)