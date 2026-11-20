import pytest
from helpers import acme_v2, read_policy

from app.chunking import PolicyFormatError
from app.ingest import IngestError, ingest_policy
from app.retrieval import retrieve

Q = 'women employees security escort after what time'


def test_new_version_replaces_old(store):
    ingest_policy(store, 'acme', acme_v2())
    assert store.active_version('acme') == 2
    hits = retrieve(store, 'acme', Q, k=6)
    assert hits and all(h.version == 2 for h in hits)
    assert any('9 PM' in h.text for h in hits)
    assert not any('8 PM' in h.text for h in hits)
    assert store.chunks.get(ids=['acme-v1-s2'])['ids'] == []      # old chunks removed


def test_same_or_older_version_rejected(store):
    with pytest.raises(IngestError):
        ingest_policy(store, 'acme', read_policy('acme'))


def test_malformed_policy_leaves_active_untouched(store):
    with pytest.raises(PolicyFormatError):
        ingest_policy(store, 'acme', 'garbage')
    assert store.active_version('acme') == 1


def test_embedding_failure_leaves_old_policy_answering(store):
    def boom(texts):
        raise RuntimeError('embedding service down')
    with pytest.raises(RuntimeError):
        ingest_policy(store, 'acme', acme_v2(), embed=boom)
    assert store.active_version('acme') == 1
    assert any('8 PM' in h.text for h in retrieve(store, 'acme', Q, k=6))


def test_failure_during_activation_rolls_back(store, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError('db down')
    monkeypatch.setattr(store, 'activate', broken)
    with pytest.raises(RuntimeError):
        ingest_policy(store, 'acme', acme_v2())
    monkeypatch.undo()
    assert store.active_version('acme') == 1
    leftovers = store.chunks.get(where={'$and': [{'company': 'acme'}, {'version': 2}]})['ids']
    assert leftovers == []                                         # no half-written v2
    assert all(h.version == 1 for h in retrieve(store, 'acme', Q, k=6))
