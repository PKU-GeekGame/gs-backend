from __future__ import annotations
import OpenSSL.crypto
import pathlib
from typing import TYPE_CHECKING, List, Optional, Tuple, Dict, Literal, Union
from cryptography.hazmat.primitives import serialization

if TYPE_CHECKING:
    from .store import UserStore
    from .state import User
    from . import utils

##
## SECRET KEYS
##

#### API KEYS

# https://github.com/settings/applications/new
GITHUB_APP_ID: Optional[str] = None # None to disable this endpoint
GITHUB_APP_SECRET = 'xxx'

# https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade/quickStartType~/null/sourceType/Microsoft_AAD_IAM
MS_APP_ID: Optional[str] = None # None to disable this endpoint
MS_PRIV_KEY = '-----BEGIN PRIVATE KEY-----\n...'
MS_THUMBPRINT = 'AA11BB22CC33DD44EE55FF66AA77BB88CC99DD00'
# openssl req -x509 -newkey rsa:4096 -keyout ms.priv -out ms.pub -sha256 -days 3650 -nodes
#with open('/path/to/ms.priv') as f:
#    MS_PRIV_KEY = f.read() # '-----BEGIN PRIVATE KEY-----\n...'

IAAA_APP_ID: Optional[str] = None # None to disable this endpoint
IAAA_KEY = 'xxx'

CARSI_APP_ID: Optional[str] = None # None to disable this endpoint
CARSI_DOMAIN = 'spoauth2pre.carsi.edu.cn'
CARSI_APP_SECRET = 'xxx'
CARSI_DEFAULT_IDP: Optional[str] = None
CARSI_PRIV_KEY: Optional[OpenSSL.crypto.PKey] = None
# https://carsi.atlassian.net/wiki/spaces/CAW/pages/27103892/3.+CARSI+SP+OAuth+Joining+CARSI+for+OAuth+SP
#with open('/path/to/carsi.priv') as f:
#    CARSI_PRIV_KEY = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM, f.read())

FEISHU_WEBHOOK_ADDR: Optional[str] = 'https://open.feishu.cn/open-apis/bot/v2/hook/...' # None to disable feishu push

#### RANDOM BULLSHITS

ADMIN_SESSION_SECRET = 'some_long_random_string'
GLITTER_SSRF_TOKEN = 'some_long_random_string'
ADMIN_2FA_COOKIE = 'some_long_random_string'

#### SIGNING KEYS

# openssl ecparam -name secp256k1 -genkey -noout -out token.priv
# openssl req -x509 -key token.priv -out token.pub -days 365
with open('/path/to/token.priv', 'rb') as f:
    TOKEN_SIGNING_KEY = serialization.load_pem_private_key(
        f.read(),
        password=None,
    )

##
## DEPLOYMENT CONFIG
##

#### DATABASE CONNECTORS

DB_CONNECTOR = 'mysql+pymysql://username:password@host:port/database?charset=utf8mb4'

#### FS PATHS

TEMPLATE_PATH = pathlib.Path('/path/to/templates').resolve()
WRITEUP_PATH = pathlib.Path('/path/to/writeups').resolve()
ATTACHMENT_PATH = pathlib.Path('/path/to/attachments').resolve()
MEDIA_PATH = pathlib.Path('/path/to/media').resolve()
SYBIL_LOG_PATH = pathlib.Path('/path/to/anticheat_log').resolve()
SCORE_OFFSET_PATH = pathlib.Path('/path/to/score_offset.json').resolve()

#### INTERNAL PORTS

GLITTER_ACTION_SOCKET_ADDR = 'ipc:///path/to/action.sock'
GLITTER_EVENT_SOCKET_ADDR = 'ipc:///path/to/event.sock'

N_WORKERS = 4

def WORKER_API_SERVER_ADDR(idx0: int) -> Tuple[str, int]:
    return '127.0.0.1', 8010+idx0

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

ADMIN_URL = '/admin' # prefix of all admin urls
ATTACHMENT_URL : Optional[str] = '/_internal_attachments' # None to opt-out X-Accel-Redirect

BACKEND_HOSTNAME = 'your_contest.example.com' # used for oauth redirects
BACKEND_SCHEME: Union[Literal['http'], Literal['https']] = 'http' # used for oauth redirects and cookies

OAUTH_HTTP_PROXIES: Optional[Dict[str, Optional[str]]] = {
    # will be passed to `httpx.AsyncClient`, see https://www.python-httpx.org/advanced/#http-proxying
    'all://*github.com': None, #'http://127.0.0.1:xxxx',
}

def BUILD_LOGIN_FINISH_URL(user: Optional[User], is_register: bool) -> str: # redirected to this after (successful or failed) login
    base = '/'
    if user and is_register:
        return base + '#/user/terms'
    else:
        return base

def BUILD_OAUTH_CALLBACK_URL(url: str) -> str:
    return url # change this if you want to rewrite the oauth callback url

##
## PERMISSION
##

MANUAL_AUTH_ENABLED = True # it should be disabled in production after setting up

REGISTRATION_ENABLED = True # can register new user; if set to false, only existing users can login

def IS_ADMIN(user: UserStore) -> bool:
    ADMIN_UIDS = [1]
    return (
        user is not None
        and user.id in ADMIN_UIDS
    )

def IS_DESTRUCTIVE_ADMIN(user: UserStore) -> bool:
    WRITABLE_ADMIN_UIDS = [1]
    return (
        user is not None
        and user.id in WRITABLE_ADMIN_UIDS
    )
