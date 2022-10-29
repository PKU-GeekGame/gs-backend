import random
import markdown
from markdown.postprocessors import Postprocessor
from markdown.extensions import Extension
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.md_in_html import MarkdownInHtmlExtension
from markdown.extensions.tables import TableExtension
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.sane_lists import SaneListExtension
import datetime
import pytz
import base64
import OpenSSL.crypto
import traceback
import asyncio
import secrets
from typing import Union, Callable

from . import secret

def gen_random_str(length: int = 32, *, crypto: bool = False) -> str:
    choice: Callable[[str], str] = secrets.choice if crypto else random.choice  # type: ignore
    alphabet = 'qwertyuiopasdfghjkzxcvbnmQWERTYUPASDFGHJKLZXCVBNM23456789'

    return ''.join([choice(alphabet) for _ in range(length)])

class LinkTargetExtension(Extension):
    class LinkTargetProcessor(Postprocessor):
        def run(self, text: str) -> str:
            return text.replace('<a ', '<a target="_blank" rel="noopener noreferrer" ')

    def extendMarkdown(self, md: markdown.Markdown) -> None:
        md.postprocessors.register(self.LinkTargetProcessor(), 'link-target-processor', 100)

markdown_processor = markdown.Markdown(extensions=[
    FencedCodeExtension(),
    CodeHiliteExtension(guess_lang=False, use_pygments=True, noclasses=True),
    MarkdownInHtmlExtension(),
    TableExtension(),
    SaneListExtension(),
    LinkTargetExtension(),
], output_format='html')

def render_template(template_str: str) -> str:
    markdown_processor.reset()
    return markdown_processor.convert(template_str)

def format_timestamp(timestamp_s: Union[float, int]) -> str:
    date = datetime.datetime.fromtimestamp(timestamp_s, pytz.timezone('Asia/Shanghai'))
    t = date.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(timestamp_s, float):
        t += f'.{int((timestamp_s%1)*1000):03d}'
    return t

def sign_token(uid: int) -> str:
    sig = base64.urlsafe_b64encode(OpenSSL.crypto.sign(secret.TOKEN_SIGNING_KEY, str(uid).encode(), 'sha256')).decode()
    return f'{uid}:{sig}'

def get_traceback(e: Exception) -> str:
    return repr(e) + '\n' + ''.join(traceback.format_exception(type(e), e, e.__traceback__))

def fix_zmq_asyncio_windows() -> None:
    # RuntimeError: Proactor event loop does not implement add_reader family of methods required for zmq.
    # zmq will work with proactor if tornado >= 6.1 can be found.
    # Use `asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())` or install 'tornado>=6.1' to avoid this error.
    try:
        if isinstance(asyncio.get_event_loop_policy(), asyncio.WindowsProactorEventLoopPolicy):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        pass