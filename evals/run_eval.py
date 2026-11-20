import argparse
import json
import math
import sys
import tempfile
import time
from pathlib import Path

from app import config
from app.answer import answer_question
from app.ingest import ingest_policy
from app.llm import FakeLLM, OpenAICompatLLM
from app.store import PolicyStore

ROOT = Path(__file__).resolve().parent.parent
COMPANIES = ['acme', 'globex', 'initech']


def norm(s):
    return ''.join(s.lower().split())


def has_any(text, spec):
    return any(alt in norm(text) for alt in spec.split('|'))


def pct(values, p):
    values = sorted(values)
    return values[max(0, math.ceil(p * len(values)) - 1)]


def judge(case, ans):
    exp, company = case['expected'], case['input']['company']
    problems = []
    cited = [c['chunk_id'] for c in ans.citations]
    if any(not cid.startswith(company + '-') for cid in ans.retrieved_ids + cited):
        problems.append('CROSS-COMPANY LEAK')
    sec, hit1, hit3 = exp.get('section'), None, None
    if sec is not None:
        secs = [cid.rsplit('-s', 1)[1] for cid in ans.retrieved_ids]
        hit1, hit3 = secs[:1] == [sec], sec in secs
    if exp.get('covered') is True:
        if ans.status != 'answered':
            problems.append(f'status={ans.status}, wanted answered')
        elif sec and not any(c['section'] == sec for c in ans.citations):
            problems.append('wrong or missing citation')
    if exp.get('covered') is False and ans.status != 'not_covered':
        problems.append(f'status={ans.status}, wanted not_covered')
    for spec in exp.get('has', []):
        if not has_any(ans.message, spec):
            problems.append('answer lacks ' + spec)
    for spec in exp.get('hasnt', []):
        if has_any(ans.message, spec):
            problems.append('answer contains forbidden ' + spec)
    return problems, hit1, hit3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fake', action='store_true', help='FakeLLM: checks plumbing and retrieval only')
    ap.add_argument('--mode', default='vector', choices=['vector', 'hybrid'])
    ap.add_argument('--repeat', type=int, default=1, help='timing runs per case (for p95)')
    ap.add_argument('--pause', type=float, default=0.0, help='seconds between calls (free-tier limits)')
    ap.add_argument('--out', default=None,
                    help='file name inside evals/ (default eval_set.jsonl, or eval_set_fake.jsonl with --fake)')
    args = ap.parse_args()
    config.RETRIEVAL_MODE = args.mode
    if not args.fake and not config.LLM_API_KEY:
        sys.exit('LLM_API_KEY is not set. Put a free Groq or Gemini key in your environment '
                 '(see README), or run with --fake for a plumbing-only check.')
    out_name = args.out or ('eval_set_fake.jsonl' if args.fake else 'eval_set.jsonl')

    store = PolicyStore(tempfile.mkdtemp())            # fresh store, so every run starts identical
    for c in COMPANIES:
        ingest_policy(store, c, (ROOT / 'policies' / f'{c}_v1.md').read_text())
    llm = FakeLLM() if args.fake else OpenAICompatLLM(
        config.LLM_BASE_URL, config.LLM_API_KEY, config.LLM_MODEL, config.LLM_TIMEOUT_S)

    lines = (ROOT / 'evals' / 'cases.jsonl').read_text().splitlines()
    cases = [json.loads(line) for line in lines if line.strip()]
    latencies, hit1s, hit3s, rows = [], [], [], []
    leaks, max_calls = 0, 0
    for case in cases:
        inp, first = case['input'], None
        for _ in range(args.repeat):
            t0 = time.perf_counter()
            ans = answer_question(store, llm, inp['company'], inp['question'])
            latencies.append(time.perf_counter() - t0)
            first = first or ans
            if args.pause:
                time.sleep(args.pause)
        problems, h1, h3 = judge(case, first)
        if h1 is not None:
            hit1s.append(h1)
            hit3s.append(h3)
        leaks += 'CROSS-COMPANY LEAK' in problems
        max_calls = max(max_calls, first.llm_calls)
        case['actual'] = {'status': first.status, 'answer': first.message,
                          'citations': [c['chunk_id'] for c in first.citations],
                          'retrieved': first.retrieved_ids}
        case['pass'] = not problems
        case['notes'] = '; '.join(x for x in [case.get('notes', '')] + problems if x)
        rows.append(case)
        print(('PASS' if case['pass'] else 'FAIL'), case['id'], '; '.join(problems))

    (ROOT / 'evals' / out_name).write_text(
        '\n'.join(json.dumps(r, ensure_ascii=False) for r in rows) + '\n')
    nc = [r for r in rows if r['expected'].get('covered') is False]
    print('\n--- summary (mode=%s, llm=%s) ---' % (args.mode, 'fake' if args.fake else config.LLM_MODEL))
    print(f'retrieval hit@1: {sum(hit1s)}/{len(hit1s)}   hit@3: {sum(hit3s)}/{len(hit3s)}')
    print(f'answer pass:     {sum(r["pass"] for r in rows)}/{len(rows)}')
    print(f'not-covered ok:  {sum(r["pass"] for r in nc)}/{len(nc)}')
    print(f'cross-company leaks: {leaks}   max LLM calls per question: {max_calls}')
    print(f'latency p50: {pct(latencies, 0.5) * 1000:.0f} ms   p95: {pct(latencies, 0.95) * 1000:.0f} ms')
    sys.exit(1 if leaks else 0)


if __name__ == '__main__':
    main()

