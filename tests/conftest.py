import os

os.environ['EMBED_BACKEND'] = 'hash'      # must be set before app modules are imported
os.environ['JWT_SECRET'] = 'test-secret'

import pytest
from helpers import COMPANIES, read_policy

from app.ingest import ingest_policy
from app.store import PolicyStore


@pytest.fixture
def store(tmp_path):
    s = PolicyStore(tmp_path / 'data')            # fresh store per test
    for c in COMPANIES:
        ingest_policy(s, c, read_policy(c))
    return s
