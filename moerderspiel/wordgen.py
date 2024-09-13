import hashlib
import random
from moerderspiel import config


class WordGenerator:
    ALLOWED_CHARACTERS = 'abcdefghijklmnopqrstuvwxyz'
    ALIASES = {'ä': 'a', 'ö': 'o', 'ü': 'u', 'ß': 's'}
    WHITESPACE_CHARACTERS = ' \t\n-_.:,;'

    def __init__(self, corpus_path: str = None):
        self.weights = {}
        if corpus_path:
            with open(corpus_path, 'r') as file:
                self.analyze(file)

    def analyze(self, file):
        last = None
        while c := file.read(1):
            c = str(c).lower()
            c = type(self).ALIASES.get(c, c)

            if c in type(self).ALLOWED_CHARACTERS:
                x = self.weights.setdefault(last, {})
                x[c] = x.get(c, 0) + 1
                last = c
            elif c in type(self).WHITESPACE_CHARACTERS:
                last = None

    def next(self, previous: str, rand: random.Random) -> str:
        return rand.choices(list(self.weights[previous].keys()), self.weights[previous].values(), k=1)[0]

    def generate(self, length: int, seed=None) -> str:
        rand = random.Random(seed)

        result = ''
        last = None
        for i in range(length):
            last = self.next(last, rand)
            result += last
        return result


default = WordGenerator(corpus_path=config.WORDGEN_CORPUS)


def generate_secret_code(salt: str, length: int) -> str:
    seed = hashlib.pbkdf2_hmac(hash_name='sha256', iterations=100000, password=config.SECRET_KEY.encode(),
                               salt=salt.encode())
    return default.generate(length, seed)
