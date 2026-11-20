from . import config, embeddings


def retrieve(store, company, question, k=None):
    k = k or config.TOP_K
    version = store.active_version(company)
    if version is None:
        return []                      # unknown company or no policy: nothing to retrieve
    vector = embeddings.embed([question])[0]
    hits = store.query(company, version, vector, k)
    # defence in depth: never trust the filter alone
    return [h for h in hits if h.company == company and h.version == version][:k]