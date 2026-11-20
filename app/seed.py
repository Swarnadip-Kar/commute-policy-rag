from pathlib import Path

from . import config
from .ingest import IngestError, ingest_policy
from .store import PolicyStore


def main(folder='policies'):
    store = PolicyStore(config.DATA_DIR)
    for path in sorted(Path(folder).glob('*_v1.md')):
        company = path.name.split('_')[0]          # acme_v1.md -> acme
        try:
            print('ingested', ingest_policy(store, company, path.read_text()))
        except IngestError as e:
            print('skipped', path.name, '-', e)


if __name__ == '__main__':
    main()