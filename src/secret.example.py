import OpenSSL.crypto
import pathlib

DB_CONNECTOR = 'mysql+pymysql://username:password@host:port/database'

ADMIN_UIDS = [1]
ADMIN_GROUPS = ['staff']

ADMIN_SESSION_SECRET = 'some_long_random_string'
FLAG_LEET_SALT = 'some_long_random_string'
GLITTER_SSRF_TOKEN = 'some_long_random_string'

TOKEN_SIGNING_KEY = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM, '-----BEGIN EC PRIVATE KEY-----\n...')

GLITTER_ACTION_SOCKET_ADDR = 'ipc:///path/to/action.sock'
GLITTER_EVENT_SOCKET_ADDR = 'ipc:///path/to/event.sock'

TEMPLATE_PATH = pathlib.Path('data/templates').resolve()

FRONTEND_PORTAL_URL = '/' # redirected to this after (successful or failed) login
ADMIN_URL = '/manage' # prefix of all admin urls