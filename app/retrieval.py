from . import config, embeddings
from .bm25 import bm25_scores


def _rrf(rankings, k=60):
    fused = {}
    for ranking in rankings:
        for pos, hit in enumerate(ranking):
            fused[hit.chunk_id] = fused.get(hit.chunk_id, 0.0) + 1.0 / (k + pos + 1)
    return fused


def retrieve(store, company, question, k=None):
    k = k or config.TOP_K
    version = store.active_version(company)
    if version is None:
        return []
    vector = embeddings.embed([question])[0]
    if config.RETRIEVAL_MODE == 'hybrid':
        vec_hits = store.query(company, version, vector, max(k, 6))
        pool = store.all_chunks(company, version)          # same company and version only
        scores = bm25_scores(question, [h.section_title + '. ' + h.text for h in pool])
        ranked = sorted(zip(scores, pool), key=lambda p: p[0], reverse=True)
        lexical = [h for s, h in ranked if s > 0]
        fused = _rrf([vec_hits, lexical])
        by_id = {h.chunk_id: h for h in vec_hits + lexical}
        hits = [by_id[i] for i in sorted(fused, key=fused.get, reverse=True)]
    else:
        hits = store.query(company, version, vector, k)
    return [h for h in hits if h.company == company and h.version == version][:k]
