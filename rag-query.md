# RAG query API

POST endpoint to run a retrieval-augmented generation query against a knowledge collection.

## Example

```bash
curl -sS -X POST http://192.168.86.179:30183/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "what is taixing visa",
    "collection_base": "taixing_knowledge",
    "request_id": "req-abc123",
    "session_id": "ses-xyz789",
    "k": 5,
    "k_max": 40
  }' | jq .
echo
```

#### Concurrency Sweep Benchmark for Throughput & Tail Latency

Sweeps concurrent in-flight requests to measure success rate, mean end-to-end latency, and p99 `time_total` from curl. Each request uses a distinct `request_id` / `session_id` so traces stay separable under load.

```bash
percentile_99() {
  sort -n | awk '
    { a[NR] = $1 }
    END {
      if (NR == 0) { print "NA"; exit }
      idx = int(NR * 0.99)
      if (idx < 1) idx = 1
      if (idx > NR) idx = NR
      print a[idx]
    }'
}

RAG_URL="http://192.168.86.179:30183"
TOTAL_REQUESTS=300

echo "Benchmark start total=$TOTAL_REQUESTS"

for CONCURRENCY in 1 2 5 10 40; do
  echo "CONCURRENCY=$CONCURRENCY"
  tmpfile=$(mktemp)

  seq 1 "$TOTAL_REQUESTS" | xargs -P "$CONCURRENCY" -I{} bash -c '
    i="$1"
    base="$2"
    body=$(printf "%s" "{\"question\":\"what is taixing visa\",\"collection_base\":\"taixing_knowledge\",\"request_id\":\"req-${i}\",\"session_id\":\"ses-${i}\",\"k\":5,\"k_max\":40}")
    curl -sS -o /dev/null \
      -w "%{http_code} %{time_connect} %{time_starttransfer} %{time_total}\n" \
      -X POST "${base}/v1/rag/query" \
      -H "Content-Type: application/json" \
      -d "$body"
  ' _ {} "$RAG_URL" >"$tmpfile"

  success=$(awk '$1 == "200" { c++ } END { print c + 0 }' "$tmpfile")
  total=$(wc -l <"$tmpfile" | tr -d " ")
  errors=$((total - success))

  p99_e2e=$(awk '$1 == "200" { print $4 }' "$tmpfile" | percentile_99)
  avg_e2e=$(awk '$1 == "200" { sum += $4; c++ } END { if (c==0) print "NA"; else printf "%.6f", sum/c }' "$tmpfile")

  echo "url=$RAG_URL concurrency=$CONCURRENCY success=$success errors=$errors avg_e2e=${avg_e2e}s p99_e2e=${p99_e2e}s"

  rm -f "$tmpfile"
  echo ""
done
```

Adjust `RAG_URL`, `TOTAL_REQUESTS`, concurrency list, and the JSON fields in `printf` to match your deployment and scenario.
