from pathlib import Path

POLICIES = Path(__file__).resolve().parent.parent / 'policies'
COMPANIES = ['acme', 'globex', 'initech']


def read_policy(company, version=1):
    return (POLICIES / f'{company}_v{version}.md').read_text()


def acme_v2():
    '''Acme v2: version bumped and the escort threshold moved from 8 PM to 9 PM.'''
    return read_policy('acme').replace('version: 1', 'version: 2').replace('after 8 PM', 'after 9 PM')
