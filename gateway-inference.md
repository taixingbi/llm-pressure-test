# layer-gpu-pressure-test

## reference
###
```bash
curl http://192.168.86.179:30080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "messages": [
      {"role": "user", "content": "introduce new york city"}
    ],
    "max_tokens": 256
  }'
```

```### k3s
```bash
BASE_URL=http://192.168.86.179:30080
CHAT_JSON='{"model":"Qwen/Qwen2.5-7B-Instruct","messages":[{"role":"user","content":"introduce new york city"}],"max_tokens":256}'

for p in 60 80 100 120; do
  echo "=== concurrency $p ==="
  seq 1 200 | xargs -I{} -P "$p" sh -c '
    curl -s -o /dev/null -w "%{http_code}\n" "$0/v1/chat/completions" \
      -H "Content-Type: application/json" \
      -d "$1"
  ' "$BASE_URL" "$CHAT_JSON" | sort | uniq -c
done
```

### gateway-inference

```bash
run_chat_load() {
  label=$1
  base_url=$2
  json_payload=$3
  shift 3
  for p in "$@"; do
    echo "=== $label concurrency $p ==="
    seq 1 200 | xargs -I{} -P "$p" sh -c '
      curl -s -o /dev/null -w "%{http_code}\n" "$0/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d "$1"
    ' "$base_url" "$json_payload" | sort | uniq -c
  done
}

# dev
run_chat_load dev http://192.168.86.179:30180 \
  '{"model":"Qwen/Qwen2.5-7B-Instruct","messages":[{"role":"user","content":"introduce new york city"}],"max_tokens":256}' \
  20 40 60

# prod small request
run_chat_load "prod small" http://192.168.86.179:30380 \
  '{"model":"Qwen/Qwen2.5-7B-Instruct","messages":[{"role":"user","content":"introduce new york city"}],"max_tokens":56}' \
  20 40 60 80 100 120

# prod large request
run_chat_load "prod large" http://192.168.86.179:30380 \
  '{"model":"Qwen/Qwen2.5-7B-Instruct","messages":[{"role":"user","content":"introduce new york city"}],"max_tokens":256}' \
  20 40 60

# prod mixed request (25% large, 75% small)
SMALL='{"model":"Qwen/Qwen2.5-7B-Instruct","messages":[{"role":"user","content":"introduce new york city"}],"max_tokens":64}'
LARGE='{"model":"Qwen/Qwen2.5-7B-Instruct","messages":[{"role":"user","content":"Write a detailed 8-section travel guide for New York City including history, neighborhoods, transportation, food, attractions, itinerary, budget tips, and safety advice."}],"max_tokens":512}'
BASE=http://192.168.86.179:30380

for p in 40 60 80; do
  echo "=== mixed random concurrency $p ==="
  seq 1 200 | xargs -I{} -P "$p" bash -c '
    r=$((RANDOM % 4))
    if [ "$r" -eq 0 ]; then
      TYPE=large
      DATA='"'"$LARGE"'"'
    else
      TYPE=small
      DATA='"'"$SMALL"'"'
    fi
    code=$(curl -s -o /dev/null -w "%{http_code}" "'"$BASE"'/v1/chat/completions" \
      -H "Content-Type: application/json" \
      -d "$DATA")
    echo "$TYPE $code"
  ' | sort | uniq -c
done
```
