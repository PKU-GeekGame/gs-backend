from __future__ import annotations
import OpenSSL.crypto
import pathlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .store import UserStore

##
## SECRET KEYS
##

#### API KEYS

GITHUB_APP_ID = 'xxx'
GITHUB_APP_SECRET = 'xxx'

MS_APP_ID = 'xxx'
MS_APP_SECRET = 'xxx'

FEISHU_WEBHOOK_ADDR = 'https://open.feishu.cn/open-apis/bot/v2/hook/...'

#### RANDOM BULLSHITS

ADMIN_SESSION_SECRET = 'some_long_random_string'
FLAG_LEET_SALT = 'some_long_random_string'
GLITTER_SSRF_TOKEN = 'some_long_random_string'

#### SIGNING KEYS

with open('/path/to/token.priv') as f:
    TOKEN_SIGNING_KEY = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM, f.read())

##
## DEPLOYMENT CONFIG
##

#### DATABASE CONNECTORS

DB_CONNECTOR = 'mysql+pymysql://username:password@host:port/database'

#### FS PATHS

TEMPLATE_PATH = pathlib.Path('/path/to/templates').resolve()
WRITEUP_PATH = pathlib.Path('/path/to/writeups').resolve()
ATTACHMENT_PATH = pathlib.Path('/path/to/attachments').resolve()
MEDIA_PATH = pathlib.Path('/path/to/media').resolve()

WRITEUP_MAX_SIZE_MB = 20

#### INTERNAL PORTS

GLITTER_ACTION_SOCKET_ADDR = 'ipc:///path/to/action.sock'
GLITTER_EVENT_SOCKET_ADDR = 'ipc:///path/to/event.sock'

N_WORKERS = 4

WORKER_API_SERVER_KWARGS = lambda idx0: { # will be passed to `Sanic.run`
    'host': '127.0.0.1',
    'port': 8010+idx0,
    'debug': False,
    'access_log': False, # nginx already does this. disabling sanic access log makes it faster.
}

REDUCER_ADMIN_SERVER_ADDR = ('127.0.0.1', 5000)

#### URLS

FRONTEND_PORTAL_URL = '/' # redirected to this after (successful or failed) login
ADMIN_URL = '/admin' # prefix of all admin urls
ATTACHMENT_URL = '/_internal_attachments' # or `None` to opt-out X-Accel-Redirect

BACKEND_HOSTNAME = 'your_contest.example.com' # used for oauth redirects
BACKEND_SCHEME = 'https' # used for oauth redirects

OAUTH_HTTP_PROXIES = { # will be passed to `httpx.AsyncClient`, see https://www.python-httpx.org/advanced/#http-proxying
    'all://*github.com': None, #'http://127.0.0.1:xxxx',
}

##
## PERMISSION
##

def IS_ADMIN(user: UserStore) -> bool:
    ADMIN_UIDS = [1]
    ADMIN_GROUPS = ['staff']
    return (
        user is not None
        and user.group in ADMIN_GROUPS
        and user.id in ADMIN_UIDS
    )
