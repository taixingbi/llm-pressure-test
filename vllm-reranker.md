# vLLM embedding (direct nodes)

  --model BAAI/bge-reranker-v2-m3 \
  --runner pooling \
  --convert classify \
  --host 0.0.0.0 \
  --port 8002 \
  --dtype half \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.01
  
## Single-request smoke

gpu-node-1:

```bash
curl -sS http://192.168.86.173:8002/v1/rerank \
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

curl -sS http://192.168.86.173:8002/v1/rerank \
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

##### test network
```bash
BACKEND="http://192.168.86.173:8002"
MODEL="BAAI/bge-reranker-v2-m3"
INPUT_CHARS=8000
TOTAL=500
CONCURRENCY=20

DOC=$(python3 - <<'PY'
print(("Paris is the capital of France. " * 300)[:8000])
PY
)

tmp=$(mktemp)

seq 1 "$TOTAL" | xargs -I{} -P "$CONCURRENCY" bash -c '
  curl -s -o /dev/null \
    -w "%{http_code} %{time_starttransfer} %{time_total}\n" \
    "'"$BACKEND"'/v1/rerank" \
    -H "Content-Type: application/json" \
    -d "$(jq -n \
      --arg model "'"$MODEL"'" \
      --arg query "What is Paris?" \
      --arg doc "'"$DOC"'" \
      --arg doc2 "Berlin is the capital of Germany." \
      '"'"'{
        model: $model,
        query: $query,
        documents: [$doc, $doc2],
        top_n: 2
      }'"'"')"
' > "$tmp"

awk -v backend="$BACKEND" \
    -v input_chars="$INPUT_CHARS" \
    -v approx_tokens="$((INPUT_CHARS / 4))" \
    -v total="$TOTAL" '
{
  code=$1
  ttfb[NR]=$2
  e2e[NR]=$3
  if (code >= 200 && code < 300) success++
  else errors++
}
function p99(arr, n,    i,j,t,idx) {
  delete sorted
  for (i=1;i<=n;i++) sorted[i]=arr[i]
  for (i=1;i<=n;i++)
    for (j=i+1;j<=n;j++)
      if (sorted[i] > sorted[j]) {
        t=sorted[i]; sorted[i]=sorted[j]; sorted[j]=t
      }
  idx=int(n*0.99)
  if (idx < 1) idx=1
  return sorted[idx]
}
END {
  printf "backend=%s input_chars=%s approx_tokens=%s total=%s success=%s errors=%s p99_ttfb=%.6fs p99_e2e=%.6fs\n", \
    backend, input_chars, approx_tokens, total, success+0, errors+0, p99(ttfb, NR), p99(e2e, NR)
}' "$tmp"

rm "$tmp"
```

