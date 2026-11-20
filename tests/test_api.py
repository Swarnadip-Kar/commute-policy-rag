import time

import jwt
import pytest
from fastapi.testclient import TestClient
from helpers import COMPANIES, acme_v2

from app import main
from app.auth import issue_token
from app.llm import FakeLLM, LLMError

Q = {'question': 'women employees security escort after what time'}


@pytest.fixture
def client(store):
    main.app.dependency_overrides[main.get_store] = lambda: store
    main.app.dependency_overrides[main.get_llm] = lambda: FakeLLM()
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def auth(company, **kw):
    return {'Authorization': f'Bearer {issue_token(company, **kw)}'}


def test_no_token_is_401(client):
    assert client.post('/ask', json=Q).status_code == 401


def test_tampered_wrong_secret_expired_and_alg_none_tokens_are_401(client):
    good = issue_token('acme')
    now = int(time.time())
    claims = {'sub': 'x', 'company': 'globex', 'exp': now + 60}
    bad = [good[:-3] + 'abc',
           jwt.encode(claims, 'some-other-secret', algorithm='HS256'),
           issue_token('acme', ttl_s=-10),
           jwt.encode(claims, '', algorithm='none')]
    for token in bad:
        r = client.post('/ask', json=Q, headers={'Authorization': f'Bearer {token}'})
        assert r.status_code == 401


@pytest.mark.parametrize('company', COMPANIES)
def test_citations_belong_to_the_token_company(client, company):
    r = client.post('/ask', json=Q, headers=auth(company))
    assert r.status_code == 200 and r.json()['citations']
    assert all(c['chunk_id'].startswith(company + '-') for c in r.json()['citations'])


def test_company_in_body_is_rejected(client):
    r = client.post('/ask', json={**Q, 'company': 'globex'}, headers=auth('acme'))
    assert r.status_code == 422


def test_company_header_is_ignored(client):
    headers = {**auth('acme'), 'X-Company': 'globex'}
    r = client.post('/ask', json=Q, headers=headers)
    assert all(c['chunk_id'].startswith('acme-') for c in r.json()['citations'])


def test_llm_outage_returns_503_try_again(client):
    main.app.dependency_overrides[main.get_llm] = lambda: FakeLLM(lambda s, u: LLMError('down'))
    r = client.post('/ask', json=Q, headers=auth('acme'))
    assert r.status_code == 503 and 'try again' in r.json()['answer'].lower()


def test_employee_cannot_ingest(client):
    r = client.post('/admin/policies', json={'company': 'acme', 'text': acme_v2()}, headers=auth('acme'))
    assert r.status_code == 403


def test_after_admin_update_only_the_new_version_answers(client):
    r = client.post('/admin/policies', json={'company': 'acme', 'text': acme_v2()},
                    headers=auth('acme', role='admin'))
    assert r.status_code == 200
    r = client.post('/ask', json=Q, headers=auth('acme'))
    assert r.json()['citations'] and all(c['version'] == 2 for c in r.json()['citations'])


def test_malformed_admin_upload_is_422_and_old_policy_stays(client, store):
    r = client.post('/admin/policies', json={'company': 'acme', 'text': 'garbage'},
                    headers=auth('acme', role='admin'))
    assert r.status_code == 422 and store.active_version('acme') == 1
