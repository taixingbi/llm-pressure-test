# layer-gpu-pressure-test

## reference
### smoke test
```bash
curl http://192.168.86.179:30080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "messages": [
      {"role": "user", "content": "introduce new york city"}
    ],
    "max_tokens": 50
  }'
```

### gateway-inference

```bash
SMALL='{"model":"Qwen/Qwen2.5-7B-Instruct","messages":[{"role":"user","content":"introduce new york city"}],"max_tokens":64}'
LARGE='{"model":"Qwen/Qwen2.5-7B-Instruct","messages":[{"role":"user","content":"Write a detailed 8-section travel guide for New York City including history, neighborhoods, transportation, food, attractions, itinerary, budget tips, and safety advice."}],"max_tokens":512}'
BASE=http://192.168.86.179:30380
TOTAL=200

for p in 40 60; do
  tmp=$(mktemp)

  seq 1 "$TOTAL" | xargs -I{} -P "$p" bash -c '
    r=$((RANDOM % 4))
    if [ "$r" -eq 0 ]; then
      TYPE=large
      DATA='"'"$LARGE"'"'
    else
      TYPE=small
      DATA='"'"$SMALL"'"'
    fi

    curl -s -o /dev/null \
      -w "$TYPE %{http_code} %{time_connect} %{time_starttransfer} %{time_total}\n" \
      "'"$BASE"'/v1/chat/completions" \
      -H "Content-Type: application/json" \
      -d "$DATA"
  ' > "$tmp"

  awk -v backend="$BASE" -v concurrency="$p" -v total="$TOTAL" '
    {
      type=$1
      code=$2
      connect[NR]=$3
      ttfb[NR]=$4
      e2e[NR]=$5
      total_e2e += $5
      count[type]++
      if (code >= 200 && code < 300) success++
      else errors++
    }
    function p99(arr, n,    i, j, t, idx) {
      for (i=1;i<=n;i++) sorted[i]=arr[i]
      for (i=1;i<=n;i++)
        for (j=i+1;j<=n;j++)
          if (sorted[i] > sorted[j]) {
            t=sorted[i]; sorted[i]=sorted[j]; sorted[j]=t
          }
      idx=int(n*0.99)
      if (idx < 1) idx=1
      if (idx > n) idx=n
      return sorted[idx]
    }
    END {
      printf "backend=%s type=mixed concurrency=%s total=%d small=%d large=%d success=%d errors=%d total_e2e=%.6fs avg_e2e=%.6fs p99_connect=%.6fs p99_ttfb=%.6fs p99_e2e=%.6fs\n", \
        backend, concurrency, total, count["small"]+0, count["large"]+0, success+0, errors+0, total_e2e, total_e2e/NR, p99(connect, NR), p99(ttfb, NR), p99(e2e, NR)
    }
  ' "$tmp"

  rm -f "$tmp"
done
```
