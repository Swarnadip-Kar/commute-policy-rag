import logging

from . import embeddings
from .chunking import parse_policy

log = logging.getLogger('ingest')


class IngestError(Exception):
    '''Ingestion refused or failed. The previously active policy is untouched.'''


def ingest_policy(store, company, raw_text, embed=None):
    embed = embed or embeddings.embed
    chunks = parse_policy(company, raw_text)                 # 1. may raise, nothing touched
    version = chunks[0].version
    current = store.active_version(company)
    if current is not None and version <= current:           # 2. only newer versions
        raise IngestError(f'{company}: version {version} is not newer than active version {current}')
    vectors = embed([c.embed_text for c in chunks])           # 3. may raise, nothing touched
    try:
        store.delete_chunks(company, version)                 # leftovers of a crashed attempt
        store.add_chunks(chunks, vectors)                     # 4. invisible to retrieval
        store.activate(company, version, chunks[0].doc_title) # 5. atomic flip
    except Exception:
        try:
            store.delete_chunks(company, version)             # roll back the side-by-side write
        except Exception:
            log.exception('cleanup after failed ingestion also failed')
        raise
    if current is not None:                                   # 6. best-effort tidy-up
        try:
            store.delete_chunks(company, current)
        except Exception:
            log.exception('old chunks not deleted; harmless, filtered out by version')
    return {'company': company, 'version': version, 'sections': len(chunks)}