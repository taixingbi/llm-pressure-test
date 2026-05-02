# vLLM embedding (direct nodes)

  --model BAAI/bge-reranker-v2-m3 \
  --runner pooling \
  --convert classify \
  --host 0.0.0.0 \
  --port 8002 \
  --dtype half \
  --max-model-len 8192 \
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
BACKENDS=(
  "http://192.168.86.173:8002"
  "http://192.168.86.176:8002"
)

MODEL="BAAI/bge-reranker-v2-m3"
INPUT_CHARS=8000
TOTAL=500

DOC=$(python3 - <<'PY'
print(("Paris is the capital of France. " * 2000)[:8000])
PY
)

payload=$(mktemp)
jq -n \
  --arg model "$MODEL" \
  --arg query "What is Paris?" \
  --arg doc "$DOC" \
  --arg doc2 "Berlin is the capital of Germany." \
  '{
    model: $model,
    query: $query,
    documents: [$doc, $doc2],
    top_n: 2
  }' > "$payload"

for CONCURRENCY in 20 40 60; do
  for BACKEND in "${BACKENDS[@]}"; do
    tmp=$(mktemp)

    seq 1 "$TOTAL" | xargs -I{} -P "$CONCURRENCY" curl -s -o /dev/null \
      -w "%{http_code} %{time_starttransfer} %{time_total}\n" \
      "$BACKEND/v1/rerank" \
      -H "Content-Type: application/json" \
      -d @"$payload" > "$tmp"

    awk -v backend="$BACKEND" \
        -v input_chars="$INPUT_CHARS" \
        -v approx_tokens="$((INPUT_CHARS / 4))" \
        -v total="$TOTAL" \
        -v concurrency="$CONCURRENCY" '
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
      printf "backend=%s concurrency=%s input_chars=%s approx_tokens=%s total=%s success=%s errors=%s p99_ttfb=%.6fs p99_e2e=%.6fs\n", \
        backend, concurrency, input_chars, approx_tokens, total, success+0, errors+0, p99(ttfb, NR), p99(e2e, NR)
    }' "$tmp"

    rm "$tmp"
  done

  printf "\n"
done

rm "$payload"
```

```
backend=http://192.168.86.173:8002 concurrency=20 input_chars=8000 approx_tokens=2000 total=500 success=500 errors=0 p99_ttfb=0.488873s p99_e2e=0.488985s
backend=http://192.168.86.176:8002 concurrency=20 input_chars=8000 approx_tokens=2000 total=500 success=500 errors=0 p99_ttfb=0.515442s p99_e2e=0.515711s

backend=http://192.168.86.173:8002 concurrency=40 input_chars=8000 approx_tokens=2000 total=500 success=500 errors=0 p99_ttfb=0.930819s p99_e2e=0.930974s
backend=http://192.168.86.176:8002 concurrency=40 input_chars=8000 approx_tokens=2000 total=500 success=500 errors=0 p99_ttfb=1.220140s p99_e2e=1.257546s

backend=http://192.168.86.173:8002 concurrency=60 input_chars=8000 approx_tokens=2000 total=500 success=500 errors=0 p99_ttfb=1.386318s p99_e2e=1.386575s
backend=http://192.168.86.176:8002 concurrency=60 input_chars=8000 approx_tokens=2000 total=500 success=500 errors=0 p99_ttfb=1.395978s p99_e2e=1.396207s
```

