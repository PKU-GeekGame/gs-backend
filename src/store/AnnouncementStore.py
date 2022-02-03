from sqlalchemy import Column, BigInteger, Text
import time

from . import Table

class AnnouncementStore(Table):
    __tablename__ = 'announcement'

    timestamp_s = Column(BigInteger, nullable=False, default=lambda: int(time.time()))
    content_template = Column(Text, nullable=False)