import OpenSSL.crypto

DB_CONNECTOR = 'mysql+pymysql://username:password@host:port/database'

ADMIN_SESSION_SECRET = '...'

FLAG_LEET_SALT = '...'

GLITTER_SSRF_TOKEN = '...'

TOKEN_SIGNING_KEY = OpenSSL.crypto.load_privatekey(OpenSSL.crypto.FILETYPE_PEM, '-----BEGIN EC PRIVATE KEY-----\n...')