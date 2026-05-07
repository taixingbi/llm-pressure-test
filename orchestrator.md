# RAG query API

POST endpoint to run a retrieval-augmented generation query against a knowledge collection.

## Example

```bash
curl -N -s -X POST http://192.168.86.179:30184/orchestrator/stream-answer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "ses-123",
    "request_id": "req-123",
    "question": "what is taixing visa status?"
  }'
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

ORCH_URL="http://192.168.86.179:30184"
echo "Benchmark start (requests per level = 2 * concurrency)"

for CONCURRENCY in 1 10 20; do
  TOTAL_REQUESTS=$((CONCURRENCY * 2))
  echo "CONCURRENCY=$CONCURRENCY TOTAL_REQUESTS=$TOTAL_REQUESTS"
  tmpfile=$(mktemp)

  seq 1 "$TOTAL_REQUESTS" | xargs -P "$CONCURRENCY" -I{} bash -c '
    i="$1"
    base="$2"
    body=$(printf "%s" "{\"question\":\"what is taixing visa status?\",\"request_id\":\"req-${i}\",\"session_id\":\"ses-${i}\"}")
    curl -sS -o /dev/null \
      -w "%{http_code} %{time_connect} %{time_starttransfer} %{time_total}\n" \
      -X POST "${base}/orchestrator/stream-answer" \
      -H "Content-Type: application/json" \
      -d "$body"
  ' _ {} "$ORCH_URL" >"$tmpfile"

  success=$(awk '$1 == "200" { c++ } END { print c + 0 }' "$tmpfile")
  total=$(wc -l <"$tmpfile" | tr -d " ")
  errors=$((total - success))

  p99_e2e=$(awk '$1 == "200" { print $4 }' "$tmpfile" | percentile_99)
  avg_e2e=$(awk '$1 == "200" { sum += $4; c++ } END { if (c==0) print "NA"; else printf "%.6f", sum/c }' "$tmpfile")
  p99_ttfb=$(awk '$1 == "200" { print $3 }' "$tmpfile" | percentile_99)
  avg_ttfb=$(awk '$1 == "200" { sum += $3; c++ } END { if (c==0) print "NA"; else printf "%.6f", sum/c }' "$tmpfile")

  echo "url=$ORCH_URL concurrency=$CONCURRENCY success=$success errors=$errors avg_ttfb=${avg_ttfb}s p99_ttfb=${p99_ttfb}s avg_e2e=${avg_e2e}s p99_e2e=${p99_e2e}s"

  rm -f "$tmpfile"
  echo ""
done
```

Adjust `ORCH_URL`, concurrency list, multiplier logic (`TOTAL_REQUESTS=$((CONCURRENCY * 2))`), and the JSON fields in `printf` to match your deployment and scenario.
