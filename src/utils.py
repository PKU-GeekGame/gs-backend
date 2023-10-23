import random
import time
import importlib.util
from types import ModuleType
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
from pathlib import Path
import os
import sys
import psutil
import re
import jinja2
from contextlib import contextmanager
from typing import Union, Callable, Dict, Any, Iterator, Literal

LogLevel = Literal['debug', 'info', 'warning', 'error', 'critical', 'success']

from . import secret

def gen_random_str(length: int = 32, *, crypto: bool = False) -> str:
    choice: Callable[[str], str] = secrets.choice if crypto else random.choice  # type: ignore
    alphabet = 'qwertyuiopasdfghjkzxcvbnmQWERTYUPASDFGHJKLZXCVBNM23456789'

    return ''.join([choice(alphabet) for _ in range(length)])

class LinkTargetExtension(Extension):
    class LinkTargetProcessor(Postprocessor):
        EXT_LINK_RE = re.compile(r'<a href="(?!#)') # only external links

        def run(self, text: str) -> str:
            return self.EXT_LINK_RE.sub('<a target="_blank" rel="noopener noreferrer" href="', text)

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

def render_template(template_str: str, args: Dict[str, Any]) -> str:
    # jinja2 to md
    env = jinja2.Environment(
        loader=jinja2.DictLoader({'index.md': template_str}),
        autoescape=True,
        auto_reload=False,
    )
    md_str = env.get_template('index.md').render(**args)

    # md to str
    markdown_processor.reset()
    return markdown_processor.convert(md_str)

def format_timestamp(timestamp_s: Union[float, int]) -> str:
    date = datetime.datetime.fromtimestamp(timestamp_s, pytz.timezone('Asia/Shanghai'))
    t = date.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(timestamp_s, float):
        t += f'.{int((timestamp_s%1)*1000):03d}'
    return t

def format_size(size: int) -> str:
    if size<1024:
        return f'{size}B'
    elif size<1024**2:
        return f'{size/1024:.1f}K'
    elif size<1024**3:
        return f'{size/(1024**2):.1f}M'
    else:
        return f'{size/(1024**3):.1f}G'

def sign_token(uid: int) -> str:
    sig = base64.urlsafe_b64encode(OpenSSL.crypto.sign(secret.TOKEN_SIGNING_KEY, str(uid).encode(), 'sha256')).decode()
    return f'{uid}:{sig}'

def get_traceback(e: Exception) -> str:
    return repr(e) + '\n' + ''.join(traceback.format_exception(type(e), e, e.__traceback__))

def fix_zmq_asyncio_windows() -> None:
    # RuntimeError: Proactor event loop does not implement add_reader family of methods required for zmq.
    # zmq will work with proactor if tornado >= 6.1 can be found.
    # Use `asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())` or install 'tornado>=6.1' to avoid this error.
    if sys.platform=='win32':
        try:
            if isinstance(asyncio.get_event_loop_policy(), asyncio.WindowsProactorEventLoopPolicy):
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except AttributeError:
            pass

@contextmanager
def log_slow(logger: Callable[[LogLevel, str, str], None], module: str, func: str, threshold: float = 0.3) -> Iterator[None]:
    t1 = time.monotonic()
    try:
        yield
    finally:
        t2 = time.monotonic()
        if t2-t1 > threshold:
            logger('warning', module, f'took {t2-t1:.2f}s to {func}')

@contextmanager
def chdir(wd: Union[str, Path]) -> Iterator[None]:
    curdir = os.getcwd()
    try:
        os.chdir(wd)
        yield
    finally:
        os.chdir(curdir)

def sys_status() -> Dict[str, Union[int, float]]:
    load_1, load_5, load_15 = psutil.getloadavg()
    vmem = psutil.virtual_memory()
    smem = psutil.swap_memory()
    disk = psutil.disk_usage('/')
    G = 1024**3

    return {
        'process': len(psutil.pids()),

        'n_cpu': psutil.cpu_count(logical=False),
        'load_1': load_1,
        'load_5': load_5,
        'load_15': load_15,

        'ram_total': vmem.total/G,
        'ram_used': vmem.used/G,
        'ram_free': vmem.available/G,

        'swap_total': smem.total/G,
        'swap_used': smem.used/G,
        'swap_free': smem.free/G,

        'disk_total': disk.total/G,
        'disk_used': disk.used/G,
        'disk_free': disk.free/G,
    }

def load_module(file_path: Path) -> ModuleType:
    # https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
    spec = importlib.util.spec_from_file_location('_dyn_module', str(file_path))
    assert spec is not None and spec.loader is not None # no import loader in this env, which is weird

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
