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
- http://192.168.86.179:30182 is the gateway (same /v1/rerank JSON as direct).
- Bump CONCURRENCY until you hit queueing or errors; compare with vLLM --max-num-seqs.
- Gateway adds proxy/routing overhead; include trace headers only on the gateway path below.
backend=http://192.168.86.173:8002 type=direct text_chars=79 approx_tokens=19 total=500 success=500 errors=0 total_e2e=71.311712s avg_e2e=0.142623s p99_connect=1.022341s p99_ttfb=1.111249s p99_e2e=1.111287s
backend=http://192.168.86.176:8002 type=direct text_chars=79 approx_tokens=19 total=500 success=500 errors=0 total_e2e=84.730925s avg_e2e=0.169462s p99_connect=1.101569s p99_ttfb=1.136427s p99_e2e=1.137096s
backend=http://192.168.86.179:30182 type=gateway text_chars=79 approx_tokens=19 total=500 success=500 errors=0 total_e2e=99.676760s avg_e2e=0.199354s p99_connect=0.162973s p99_ttfb=0.316638s p99_e2e=0.316701s
h@taixing-macmini ~ % clear

h@taixing-macmini ~ % >....                                                                                                                                                                                                         
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
zsh: command not found: #
[1] 23420
zsh: command not found: #
[1]  + exit 127   # 计算 chars
zsh: command not found: tokens
NOTE:
- direct backends: 173 / 176
- gateway: http://192.168.86.179:30182
- chars=8001 tokens~2000
- CONCURRENCY=80 TOTAL=500
backend=http://192.168.86.173:8002 type=direct text_chars=8001 approx_tokens=2000 total=500 success=500 errors=0 total_e2e=941.887320s avg_e2e=1.883775s p99_connect=1.013120s p99_ttfb=2.925260s p99_e2e=2.925451s
backend=http://192.168.86.176:8002 type=direct text_chars=8001 approx_tokens=2000 total=500 success=500 errors=0 total_e2e=933.164636s avg_e2e=1.866329s p99_connect=0.141272s p99_ttfb=2.071264s p99_e2e=2.071351s
backend=http://192.168.86.179:30182 type=gateway text_chars=8001 approx_tokens=2000 total=500 success=500 errors=0 total_e2e=479.404292s avg_e2e=0.958809s p99_connect=0.199727s p99_ttfb=1.140478s p99_e2e=1.143421s
```
