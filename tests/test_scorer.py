from app.answer import Answer
from evals.run_eval import has_any, judge


def test_has_any_ignores_case_and_spaces_and_supports_alternatives():
    assert has_any('Escort after 8 PM.', '8pm|20:00')
    assert has_any('at least 4 hours', '4hours')
    assert not has_any('after 10 PM', '8pm')


def test_scorer_catches_a_cross_company_leak():
    case = {'input': {'company': 'acme', 'question': 'q'}, 'expected': {'covered': True, 'section': '2'}}
    ans = Answer('answered', 'ok', [{'chunk_id': 'globex-v1-s2', 'section': '2'}],
                 ['globex-v1-s2', 'acme-v1-s2'], 1)
    problems, _, _ = judge(case, ans)
    assert 'CROSS-COMPANY LEAK' in problems


def test_scorer_flags_forbidden_fact_and_wrong_status():
    case = {'input': {'company': 'acme', 'question': 'q'},
            'expected': {'covered': False, 'hasnt': ['10pm']}}
    ans = Answer('answered', 'Escort after 10 PM', [], ['acme-v1-s2'], 1)
    problems, _, _ = judge(case, ans)
    assert any('forbidden' in p for p in problems) and any('wanted not_covered' in p for p in problems)
