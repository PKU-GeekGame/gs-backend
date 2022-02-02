import random

def gen_random_token(length=32):
    ALPHABET='qwertyuiopasdfghjkzxcvbnmQWERTYUPASDFGHJKLZXCVBNM23456789'
    return ''.join([random.choice(ALPHABET) for _ in range(length)])