import random
import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.md_in_html import MarkdownInHtmlExtension
from markdown.extensions.tables import TableExtension
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.sane_lists import SaneListExtension
import datetime
import pytz
import base64
import OpenSSL
import traceback
from typing import Union

from . import secret

def gen_random_str(length: int = 32) -> str:
    ALPHABET='qwertyuiopasdfghjkzxcvbnmQWERTYUPASDFGHJKLZXCVBNM23456789'
    return ''.join([random.choice(ALPHABET) for _ in range(length)])

def render_template(template_str: str) -> str:
    return markdown.markdown(template_str, extensions=[
        FencedCodeExtension(),
        CodeHiliteExtension(guess_lang=False, use_pygments=True, noclasses=True),
        MarkdownInHtmlExtension(),
        TableExtension(),
        SaneListExtension(),
    ], output_format='html')

def format_timestamp(timestamp_s: Union[float, int]) -> str:
    date = datetime.datetime.fromtimestamp(timestamp_s, pytz.timezone('Asia/Shanghai'))
    return date.strftime('%Y-%m-%d %H:%M:%S')

def sign_token(uid: int) -> str:
    sig = base64.b64encode(OpenSSL.crypto.sign(secret.TOKEN_SIGNING_KEY, str(uid).encode(), 'sha256')).decode()
    return f'{uid}:{sig}'

def get_traceback(e: Exception) -> str:
    return repr(e) + '\n' + ''.join(traceback.format_exception(type(e), e, e.__traceback__))