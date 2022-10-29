from sqlalchemy import Column, BigInteger, Text
import time

from . import Table
from .. import utils

class AnnouncementStore(Table):
    __tablename__ = 'announcement'

    timestamp_s: int = Column(BigInteger, nullable=False, default=lambda: int(time.time()))
    title = Column(Text, nullable=False)
    content_template: str = Column(Text, nullable=False)

    def __repr__(self) -> str:
        return f'[@{utils.format_timestamp(self.timestamp_s)} {self.title}]'