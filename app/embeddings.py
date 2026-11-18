import hashlib
import math
import re

from . import config

DIM = 512
TOKEN = re.compile(r'[a-z0-9]+')
STOP = {'the', 'a', 'an', 'is', 'are', 'to', 'of', 'in', 'on', 'at', 'for', 'and', 'or',
        'be', 'i', 'my', 'me', 'do', 'does', 'can', 'what', 'how', 'when', 'who', 'will',
        'it', 'if', 'by', 'as', 'with', 'from', 'that', 'this'}


def tokenize(text):
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP]


def _hash_embed(text):
    vec = [0.0] * DIM
    for tok in tokenize(text):
        idx = int(hashlib.md5(tok.encode()).hexdigest(), 16) % DIM
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]          # unit length, so distance ~ cosine


_minilm = None


def _minilm_embed(texts):
    global _minilm
    if _minilm is None:                      # loaded once, then reused
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        _minilm = DefaultEmbeddingFunction()
    return [[float(x) for x in v] for v in _minilm(texts)]


def embed(texts):
    if config.EMBED_BACKEND == 'hash':
        return [_hash_embed(t) for t in texts]
    return _minilm_embed(texts)