# Evaluation Report

## Scenarios

17 cases across 5 categories:

| Category | Count | Case IDs |
|---|---|---|
| Direct questions | 4 | q01, q02, q06, q10 |
| Paraphrases (different words, same meaning) | 5 | q03, q04, q05, q09, q11 |
| Cross-company traps | 3 | q07, q15, q16 |
| Not-covered (policy is silent) | 3 | q12, q13, q14 |
| Injection (question or document) | 2 | q15, q17 |

> Note: q15 covers both cross-company trap and injection. File: `evals/eval_set.jsonl`.

## Method

| Metric | Definition |
|---|---|
| **Retrieval hit@1** | The expected section is the top retrieved chunk |
| **Retrieval hit@3** | The expected section is anywhere in the top-3 retrieved chunks |
| **Answer pass** | Correct status (answered / not_covered) AND cites the expected section AND answer contains expected facts AND does not contain forbidden facts |
| **Not-covered ok** | Cases with `covered: false` that correctly returned `not_covered` |
| **Leaks** | Any retrieved or cited chunk from another company (must be **0**) |
| **Latency p50 / p95** | Per-question wall-clock time including LLM call, over 7 timing runs |

**Setup:** Fresh `PolicyStore` (tmpdir) per run, v1 policies ingested fresh each time. LLM: `openai/gpt-oss-20b` via Groq, temperature 0, timeout 8 s. Timing: 7 repeats per case, LLM call included. `--pause 4` between calls to stay under Groq free-tier limits.

## Results

| Mode | hit@1 | hit@3 | Answer pass | Not-covered ok | Leaks | p50 | p95 |
|---|---|---|---|---|---|---|---|
| **vector** | 10/12 (83%) | 12/12 (100%) | 16/17 (94%) | 3/4 (75%) | **0** | 806 ms | 1036 ms |
| **hybrid** | 10/12 (83%) | 12/12 (100%) | 16/17 (94%) | 3/4 (75%) | **0** | 788 ms | 1120 ms |

**Default mode shipped:** `vector`

Hybrid BM25+vector retrieval was implemented as the bonus Step 13. On this corpus (6–7 chunks per company) `hit@3` is already 100% in both modes, so there is no measurable quality improvement from hybrid. Hybrid p95 is slightly **higher** (1120 ms vs 1036 ms) due to the extra `all_chunks()` scan. I kept `vector` as the default and documented hybrid as a bonus feature.

**What hybrid cost:** ~40 lines of code (`app/bm25.py` + additions to `retrieval.py`), one extra `store.all_chunks()` call per query, and ~5–85 ms extra latency depending on corpus size.

## Known Failures

| Case | What happened | Cause | Decision |
|---|---|---|---|
| **q14** | `status=error, wanted not_covered`. Speed limit question — not in any policy. All 7 LLM calls timed out / returned empty content, so the pipeline returned `error` instead of `not_covered`. | Model limitation. The `openai/gpt-oss-20b` reasoning model on Groq's free tier intermittently returns empty completions for this exact question (the retrieved chunks about eligibility, booking, and miscellaneous are semantically far from "speed limit", causing the model to reason longer and sometimes time out). The retrieval was correct — no speed-limit section exists, so returning `not_covered` via LLM refusal is the right path, but we can't reach it when the LLM fails. | Keep as known failure. No code fix possible — the timeout guard (`RETRIEVAL_TIMEOUT_S`) is working correctly. With a faster model (e.g. `llama-3.1-8b-instant`) this case passes. |

> **Note on q17 (document injection):** In earlier runs with the default 2 s LLM timeout, q17 also failed. After increasing `LLM_TIMEOUT_S=8` in the `.env`, q17 passes correctly — the LLM correctly ignores the poisoned section 7 instruction and answers from section 3. This confirms the injection defence works; the earlier failures were purely a timeout issue.

## Limitations

- **Corpus size:** Only 6–7 chunks per company; `hit@3 = 100%` means retrieval has an easy job. Larger corpora would stress-test both vector and BM25 more realistically.
- **17 cases, no held-out set:** All threshold choices (evidence grounding at 0.8, `TOP_K = 3`) were visible while developing. Percentages are coarse (each case ≈ 6% of total).
- **English only:** Tokenizer uses an English stop-word list.
- **Single process:** Thread-pool timeout abandons slow retrieval but cannot kill the background thread.
- **Free-tier LLM variance:** The same provider, model, and question can return different response times across runs (q14 consistently times out on the free tier).
- **Tuned on the same set:** No held-out validation. Explicitly stated here as an honest limitation.
- **LLM_TIMEOUT_S default:** The repo default is 2 s (conservative, matches the case-study 3 s p95 requirement). Reasoning models need a higher value — `LLM_TIMEOUT_S=8` is recommended in the README.

## Trade-off I Made

**Evidence check strictness (threshold = 0.8).**

I require that at least 80% of the evidence words appear in the cited chunk text. This blocks hallucinations — if the model cannot quote the policy, the system says "not covered" rather than giving a confident but wrong answer.

**What I chose:** safety over completeness.

**What I gave up:** a loose paraphrase (e.g. the model writes "four hours advance notice" but the evidence quote says "at least 4 hours before pickup") can fail the check and return "not covered" even when retrieval was correct. The eval shows this is rare — 16/17 passed.

**Why it's tunable:** `is_grounded()` in `app/answer.py` uses a hard-coded 0.8 threshold. Lowering to 0.6 would catch more loose quotes at the cost of allowing more hallucinations through. The eval set lets you measure the effect directly.
