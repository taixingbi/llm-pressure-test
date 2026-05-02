## gateway-reranker

```bash
curl -sS http://192.168.86.179:30182/v1/rerank \
  -H "Content-Type: application/json" \
  -d '{
    "model": "BAAI/bge-reranker-v2-m3",
    "query": "What is Paris?",
    "documents": [
      "Paris is the capital of France.",
      "Berlin is the capital of Germany."
    ],
    "top_n": 2
  }' | jq
```

#### test concurrent with small tokens -> max-num-seqs

Short query + two short documents per request keeps per-seq token cost low so high concurrency stresses vLLM `--max-num-seqs` (and the gateway fan-out), not long-context throughput.

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

BACKENDS=(
  "http://192.168.86.173:8002"
  "http://192.168.86.176:8002"
  "http://192.168.86.179:30182"
)

GATEWAY_URL="http://192.168.86.179:30182"
MODEL="BAAI/bge-reranker-v2-m3"
TOTAL_REQUESTS=500
CONCURRENCY=80

# --------- 构造接近 8000 chars 的 payload ----------
PAYLOAD=$(mktemp)

LONG_DOC=$(python3 - <<'PY'
query = "What is Paris?"
doc2 = "Berlin is the capital of Germany."

target = 8000 - len(query) - len(doc2)

base = "Paris is the capital of France. "
text = (base * 500)[:target]

print(text)
PY
)

jq -n \
  --arg model "$MODEL" \
  --arg query "What is Paris?" \
  --arg doc1 "$LONG_DOC" \
  --arg doc2 "Berlin is the capital of Germany." \
  '{
    model: $model,
    query: $query,
    documents: [
      $doc1,
      $doc2
    ],
    top_n: 2
  }' >"$PAYLOAD"

# 计算 chars & tokens
text_chars=$(jq -r '.query + (.documents | join(""))' "$PAYLOAD" | wc -c | tr -d ' ')
approx_tokens=$(( text_chars / 4 ))

echo "NOTE:"
echo "- direct backends: 173 / 176"
echo "- gateway: $GATEWAY_URL"
echo "- chars=$text_chars tokens~$approx_tokens"
echo "- CONCURRENCY=$CONCURRENCY TOTAL=$TOTAL_REQUESTS"

for ENDPOINT in "${BACKENDS[@]}"; do
  tmpfile=$(mktemp)

  if [[ "$ENDPOINT" == "$GATEWAY_URL" ]]; then
    target_type="gateway"

    seq 1 "$TOTAL_REQUESTS" | xargs -P "$CONCURRENCY" -I{} bash -c '
      i="$1"
      endpoint="$2"
      payload="$3"

      curl -sS -o /dev/null \
        -w "%{http_code} %{time_connect} %{time_starttransfer} %{time_total}\n" \
        -X POST "$endpoint/v1/rerank" \
        -H "X-Request-Id: request_id_$i" \
        -H "X-Trace-Id: trace_id_$i" \
        -H "X-Session-Id: session_id_$i" \
        -H "Content-Type: application/json" \
        --data-binary @"$payload"
    ' _ {} "$ENDPOINT" "$PAYLOAD" >"$tmpfile"
  else
    target_type="direct"

    seq 1 "$TOTAL_REQUESTS" | xargs -P "$CONCURRENCY" -I{} bash -c '
      endpoint="$1"
      payload="$2"

      curl -sS -o /dev/null \
        -w "%{http_code} %{time_connect} %{time_starttransfer} %{time_total}\n" \
        -X POST "$endpoint/v1/rerank" \
        -H "Content-Type: application/json" \
        --data-binary @"$payload"
    ' _ "$ENDPOINT" "$PAYLOAD" >"$tmpfile"
  fi

  success=$(awk '$1 == "200" { c++ } END { print c + 0 }' "$tmpfile")
  total=$(wc -l <"$tmpfile" | tr -d " ")
  errors=$((total - success))

  p99_connect=$(awk '$1 == "200" { print $2 }' "$tmpfile" | percentile_99)
  p99_ttfb=$(awk '$1 == "200" { print $3 }' "$tmpfile" | percentile_99)
  p99_e2e=$(awk '$1 == "200" { print $4 }' "$tmpfile" | percentile_99)

  total_e2e=$(awk '$1 == "200" { sum += $4 } END { printf "%.6f", sum + 0 }' "$tmpfile")
  avg_e2e=$(awk '$1 == "200" { sum += $4; c++ } END { if (c == 0) print "NA"; else printf "%.6f", sum / c }' "$tmpfile")

  echo "backend=$ENDPOINT type=$target_type text_chars=$text_chars approx_tokens=$approx_tokens total=$total success=$success errors=$errors total_e2e=${total_e2e}s avg_e2e=${avg_e2e}s p99_connect=${p99_connect}s p99_ttfb=${p99_ttfb}s p99_e2e=${p99_e2e}s"

  rm -f "$tmpfile"
done

rm -f "$PAYLOAD"
```
