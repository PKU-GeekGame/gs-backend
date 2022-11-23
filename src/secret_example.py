from __future__ import annotations
import OpenSSL.crypto
import pathlib
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from .store import UserStore
    from . import utils

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
GLITTER_SSRF_TOKEN = 'some_long_random_string'
ADMIN_2FA_COOKIE = 'some_long_random_string'

#### SIGNING KEYS

# openssl ecparam -name secp256k1 -genkey -noout -out token.priv
# openssl req -x509 -key token.priv -out token.pub -days 365
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
SYBIL_LOG_PATH = pathlib.Path('/path/to/anticheat_log').resolve()

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

#### FUNCTIONS

WRITEUP_MAX_SIZE_MB = 20
WS_PUSH_ENABLED = True
POLICE_ENABLED = True
ANTICHEAT_RECEIVER_ENABLED = True

STDOUT_LOG_LEVEL: List[utils.LogLevel] = ['debug', 'info', 'warning', 'error', 'critical', 'success']
DB_LOG_LEVEL: List[utils.LogLevel] = ['info', 'warning', 'error', 'critical', 'success']
PUSH_LOG_LEVEL: List[utils.LogLevel] = ['error', 'critical']

#### URLS

FRONTEND_PORTAL_URL = '/' # redirected to this after (successful or failed) login
ADMIN_URL = '/admin' # prefix of all admin urls
ATTACHMENT_URL = '/_internal_attachments' # or `None` to opt-out X-Accel-Redirect

BACKEND_HOSTNAME = 'your_contest.example.com' # used for oauth redirects
BACKEND_SCHEME = 'https' # used for oauth redirects

OAUTH_HTTP_PROXIES = { # will be passed to `httpx.AsyncClient`, see https://www.python-httpx.org/advanced/#http-proxying
    'all://*github.com': None, #'http://127.0.0.1:xxxx',
}

def BUILD_OAUTH_CALLBACK_URL(url: str) -> str:
    return url # change this if you want to rewrite the oauth callback url

##
## PERMISSION
##

MANUAL_AUTH_ENABLED = True # it should be disabled in production after setting up

def IS_ADMIN(user: UserStore) -> bool:
    ADMIN_UIDS = [1]
    return (
        user is not None
        and user.id in ADMIN_UIDS
    )