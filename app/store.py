import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import chromadb

SCHEMA = '''
CREATE TABLE IF NOT EXISTS policy_versions (
    company     TEXT NOT NULL,
    version     INTEGER NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('active', 'retired')),
    doc_title   TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    PRIMARY KEY (company, version)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_per_company
    ON policy_versions(company) WHERE status = 'active';
'''


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    company: str
    version: int
    doc_title: str
    section_no: str
    section_title: str
    text: str
    score: float = 0.0


def _where(company, version):
    return {'$and': [{'company': company}, {'version': version}]}


def _hit(chunk_id, text, meta, score=0.0):
    return Hit(chunk_id, meta['company'], meta['version'], meta['doc_title'],
               meta['section_no'], meta['section_title'], text, score)


class PolicyStore:
    def __init__(self, data_dir):
        data_dir = Path(data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = str(data_dir / 'meta.db')
        with closing(self._conn()) as c:
            c.executescript(SCHEMA)
        client = chromadb.PersistentClient(path=str(data_dir / 'chroma'))
        self.chunks = client.get_or_create_collection('policy_chunks', embedding_function=None)

    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    # ---- versions (SQLite) ----
    def active_version(self, company):
        with closing(self._conn()) as c:
            row = c.execute("SELECT version FROM policy_versions WHERE company=? AND status='active'",
                            (company,)).fetchone()
        return row['version'] if row else None

    def activate(self, company, version, doc_title):
        '''Retire the old version and activate the new one in ONE transaction.'''
        with closing(self._conn()) as c, c:       # 'with c' = commit, or rollback on error
            c.execute("UPDATE policy_versions SET status='retired' WHERE company=? AND status='active'",
                      (company,))
            c.execute("INSERT INTO policy_versions VALUES (?, ?, 'active', ?, datetime('now'))",
                      (company, version, doc_title))

    # ---- chunks (Chroma) ----
    def add_chunks(self, chunks, vectors):
        self.chunks.add(
            ids=[c.chunk_id for c in chunks],
            embeddings=vectors,
            documents=[c.text for c in chunks],
            metadatas=[{'company': c.company, 'version': c.version, 'doc_title': c.doc_title,
                        'section_no': c.section_no, 'section_title': c.section_title} for c in chunks])

    def delete_chunks(self, company, version):
        self.chunks.delete(where=_where(company, version))

    def query(self, company, version, vector, k):
        '''Nearest chunks of ONE company and ONE version. The filter runs inside Chroma.'''
        found = self.chunks.get(where=_where(company, version), include=[])['ids']
        if not found:
            return []
        res = self.chunks.query(query_embeddings=[vector], n_results=min(k, len(found)),
                                where=_where(company, version),
                                include=['documents', 'metadatas', 'distances'])
        hits = []
        for i, cid in enumerate(res['ids'][0]):
            cosine = 1.0 - res['distances'][0][i] / 2.0   # unit vectors: L2^2 = 2 - 2cos
            hits.append(_hit(cid, res['documents'][0][i], res['metadatas'][0][i], cosine))
        return hits

    def all_chunks(self, company, version):
        res = self.chunks.get(where=_where(company, version), include=['documents', 'metadatas'])
        hits = [_hit(i, d, m) for i, d, m in zip(res['ids'], res['documents'], res['metadatas'])]
        return sorted(hits, key=lambda h: int(h.section_no))