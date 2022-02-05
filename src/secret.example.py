import OpenSSL.crypto

DB_CONNECTOR = 'mysql+pymysql://username:password@host:port/database'

ADMIN_SESSION_SECRET = '...'

FLAG_LEET_SALT = '...'

GLITTER_SSRF_TOKEN = '...'

TOKEN_SIGNING_KEY = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM, '-----BEGIN EC PRIVATE KEY-----\n...')

# DO NOT use `localhost` to replace `127.0.0.1`
# see https://stackoverflow.com/questions/6024003/why-doesnt-zeromq-work-on-localhost
GLITTER_ACTION_SOCKET_ADDR = 'tcp://127.0.0.1:5601'
GLITTER_EVENT_SOCKET_ADDR = 'tcp://127.0.0.1:5602'

API_DEBUG_MODE = False