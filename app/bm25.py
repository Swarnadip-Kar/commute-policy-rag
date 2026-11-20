import math
from collections import Counter

from .embeddings import tokenize


def bm25_scores(query, docs, k1=1.5, b=0.75):
    '''One BM25 score per document. Fine for tiny corpora; precompute for big ones.'''
    toks = [tokenize(d) for d in docs]
    n = len(docs)
    avg_len = (sum(len(t) for t in toks) / n) or 1.0
    df = Counter(w for t in toks for w in set(t))
    scores = []
    for t in toks:
        tf, s = Counter(t), 0.0
        for w in set(tokenize(query)):
            if w not in tf:
                continue
            idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
            s += idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * len(t) / avg_len))
        scores.append(s)
    return scores
