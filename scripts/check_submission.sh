#!/usr/bin/env bash
set -euo pipefail

echo '1/6 secrets scan'
if git ls-files | xargs grep -nEi '(gsk_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,}|sk-[A-Za-z0-9]{20,})'; then
  echo 'POSSIBLE KEY COMMITTED'; exit 1
fi
if git ls-files --error-unmatch .env > /dev/null 2>&1; then echo '.env is tracked'; exit 1; fi

echo '2/6 required files'
for f in README.md EVALUATION.md evals/eval_set.jsonl evals/cases.jsonl docker-compose.yml Dockerfile .env.example; do
  test -f "$f" || { echo "missing $f"; exit 1; }
done

echo '3/6 eval file format'
python -c "import json; rows=[json.loads(l) for l in open('evals/eval_set.jsonl')]; need={'id','input','expected','actual','pass','notes'}; assert len(rows)>=10 and all(need<=set(r) for r in rows) and all(r['actual'] is not None for r in rows); print(len(rows), 'cases OK')"

echo '4/6 unit tests'
python -m pytest -q

echo '5/6 docker start'
docker compose up --build -d
for i in $(seq 1 90); do curl -sf localhost:8000/health > /dev/null && break; sleep 2; done
curl -sf localhost:8000/health > /dev/null || { echo 'API did not come up'; docker compose logs api | tail -30; exit 1; }

echo '6/6 live request and isolation'
TOKEN=$(docker compose exec -T api python -m app.mint_token globex)
curl -s localhost:8000/ask -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
     -d '{"question": "After what time do women get a security escort?"}'
echo
docker compose down
echo 'ALL CHECKS PASSED'
