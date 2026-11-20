import pytest
from helpers import read_policy

from app.chunking import PolicyFormatError, parse_policy


def test_acme_has_six_sections():
    chunks = parse_policy('acme', read_policy('acme'))
    assert len(chunks) == 6
    assert chunks[1].chunk_id == 'acme-v1-s2'
    assert '8 PM' in chunks[1].text


@pytest.mark.parametrize('bad', [
    '',
    'no headings at all',
    '# T\n## 1. A\ntext',                          # no version
    '# T\nversion: 1\n',                      # no sections
    '# T\nversion: 1\n## 1. A\n',             # empty section
    '# T\nversion: 1\n## 1. A\nx\n## 1. B\ny',  # duplicate section number
])
def test_malformed_policy_rejected(bad):
    with pytest.raises(PolicyFormatError):
        parse_policy('acme', bad)


def test_bad_company_id_rejected():
    with pytest.raises(PolicyFormatError):
        parse_policy('Acme Corp!', read_policy('acme'))
