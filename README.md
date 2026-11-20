# commute-policy-rag

An assistant that answers an employee's transport questions from their own company's current policy, cites the document and section, and says plainly when the policy is silent.

## Run it (one command)

    cp .env.example .env        # put a free Groq or Gemini key in LLM_API_KEY
    docker compose up --build

The API is on http://localhost:8000 (interactive docs at `/docs`). Three policies (Acme, Globex, Initech) are loaded on start.

No key? `USE_FAKE_LLM=1 docker compose up` starts it, but `/ask` will not give real answers.

> **Reasoning model note:** If using a model with reasoning tokens (e.g. `openai/gpt-oss-20b` on Groq), set `LLM_TIMEOUT_S=8` in your `.env` — the default 2 s is too tight for the extra thinking tokens.

### Or run locally without Docker

    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python -m app.seed
    uvicorn app.main:app --port 8000

## Try it

    TOKEN=$(docker compose exec -T api python -m app.mint_token acme)
    curl -s localhost:8000/ask \
         -H "Authorization: Bearer $TOKEN" \
         -H 'Content-Type: application/json' \
         -d '{"question": "Who approves an airport trip?"}'

**Policy update (new version):**

    docker compose exec api python -m app.upload_policy acme policies/acme_v2.md

**Reset the demo:**

    docker compose down -v

## Tests and evaluation

    docker compose exec api pytest -q                   # no key needed (82 tests)
    docker compose exec api python -m evals.run_eval    # needs LLM_API_KEY; --fake checks plumbing only

**Results (vector mode, openai/gpt-oss-20b, 7 repeats per case, --pause 4):**

```
retrieval hit@1: 10/12   hit@3: 12/12
answer pass:     16/17
not-covered ok:  3/4
cross-company leaks: 0   max LLM calls per question: 1
latency p50: 806 ms   p95: 1036 ms
```

Full report: [EVALUATION.md](EVALUATION.md).

### Bonus: Hybrid Retrieval (BM25 + Vector via RRF)

Implemented in `app/bm25.py` and `app/retrieval.py` using pure-Python BM25 fused with vector search via Reciprocal Rank Fusion (RRF):

- **How to enable:** Set `RETRIEVAL_MODE=hybrid` in `.env` (or run `python -m evals.run_eval --mode hybrid`).
- **Comparison on the 17-case eval benchmark:**
  - **Vector:** hit@3 12/12 (100%), answer pass 16/17 (94%), p95 = **1036 ms**
  - **Hybrid:** hit@3 12/12 (100%), answer pass 16/17 (94%), p95 = **1120 ms**
- **Engineering decision:** On this corpus size (6–7 chunks per policy), vector search already achieves 100% hit@3. Hybrid search achieved the exact same accuracy but added ~84 ms latency and an extra full-chunk scan. We kept `vector` as the lean production default and provide `hybrid` as a tested, configurable option. Full analysis in [EVALUATION.md](EVALUATION.md).

## Design

```
Employee ── JWT ──▶ POST /ask {question}
  1. verify JWT, take company from the token (never from the body)
  2. embed question → Chroma query WHERE company = X AND version = active(X) → top 3
  3. ONE LLM call → JSON {covered, answer, cited_ids, evidence}
  4. CODE validates: cited ids ⊆ retrieved ids, evidence really is in the chunk
  5. citations built from chunk metadata, never from model text
  6. anything wrong → plain "policy does not say" or "try again" message
```

The JWT carries the `company` claim — the request body has no company field (`extra='forbid'`). Retrieval runs a Chroma `where` filter by company and active version, then re-checks in Python (defence in depth). One LLM call reads the retrieved paragraphs and phrases a short answer; code decides whether to believe it.

## How it stays inside the limits

- **At most 2 LLM calls:** one call per question; a second only if the first reply was not parseable JSON and under 1 s has elapsed.
- **At most 3 cited chunks:** `TOP_K = 3` and `MAX_CITED = 3`, both enforced in code.
- **p95 under 3 s:** measured **1036 ms** over 119 LLM calls on `openai/gpt-oss-20b` via Groq; LLM timeout is 8 s and embedding model is loaded at startup.

## Where the LLM is used, and where plain code is better

| LLM | Plain code |
|---|---|
| Read up to 3 policy paragraphs, phrase a short answer | Company from JWT, version from SQLite, retrieval filter, citation building, grounding check, timeouts, authorisation |

The model never writes citations. It only names chunk IDs; code verifies them against the retrieved set and builds citation text from metadata.

## Security

- **Company only from the signed JWT** — it is forbidden in the request body (`extra='forbid'`). No client-side override is possible.
- **Filter inside the vector query plus a second Python re-check** — if either layer ever lets a foreign chunk through, the other drops it. Zero leaks measured across 17 × 7 runs.
- **The model never writes citations** — it names IDs, code validates they are in the retrieved set and builds citation text from chunk metadata.
- **Fake tags stripped** — `_clean()` removes any `<CHUNK>` or `<QUESTION>` tags from user input and document text. The poisoned Initech section 7 is a live regression test of this.

## Trade-offs

1. **Evidence check strictness (threshold = 0.8).** Blocks hallucinations; a loose paraphrase is rejected as "not covered". Safety over completeness — tunable from the eval.
2. **Hash vs MiniLM embeddings.** Hash backend makes all 82 tests run offline and instantly. MiniLM (baked into the Docker image) is used at demo time.
3. **One LLM call, no query rewriting.** Lowest latency and cost; a badly worded question depends entirely on the embedding for retrieval.
4. **Vector vs hybrid retrieval.** Hybrid BM25+vector via RRF adds ~40 lines and was implemented as a bonus. On this 6-7 chunk corpus hit@3 is already 100% in both modes, so `vector` remains the default. The hybrid code path is tested and gated by `RETRIEVAL_MODE=hybrid`.

## Limitations

- Tiny corpus — BM25 is recomputed per query over 6–7 chunks per company.
- English only — tokenizer and stop-word list are English.
- Single process — thread-pool timeout abandons a slow retrieval but cannot kill its thread.
- Shared-secret HS256 JWT — production would use RS256.
- No rate limiting on `/ask`.
- Eval set is 17 cases — percentages are coarse; no held-out test set.
- Injection defence is layered (strip tags, code-side validation) but not absolute.

## AI assistance

I used an AI coding assistant to scaffold and complete this project following the step-by-step guide. I can explain and change every line.

## Demo video

*[Link to be added]*
