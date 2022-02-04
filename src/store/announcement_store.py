from sqlalchemy import Column, BigInteger, Text
import time

from . import Table
from .. import utils

class AnnouncementStore(Table):
    __tablename__ = 'announcement'

    timestamp_s = Column(BigInteger, nullable=False, default=lambda: int(time.time()))
    content_template = Column(Text, nullable=False)

    def __repr__(self) -> str:
        content_preview = self.content_template[:25].replace('\n', ' ')
        return f'[@{utils.format_timestamp(self.timestamp_s)} {content_preview}]'