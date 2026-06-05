# vLLM inference (direct nodes)

  --model Qwen/Qwen2.5-7B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --dtype half \
  --max-model-len 4096 \
  --max-num-seqs 32 \
  --gpu-memory-utilization 0.90

## smoke test

```bash
curl -sS http://192.168.86.173:30080/health | jq .
echo
curl -sS http://192.168.86.173:30080/v1/models | jq '.data[].id'
echo
curl -sS -o /tmp/infer_resp.json \
  -w '\nconnect=%{time_connect}s\nttfb=%{time_starttransfer}s\ne2e=%{time_total}s\n' \
  -X POST http://192.168.86.173:30080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "messages": [{"role": "user", "content": "introduce new york city"}],
    "max_tokens": 8,
    "temperature": 0
  }'

curl -sS http://192.168.86.176:30080/health | jq .
echo
curl -sS http://192.168.86.176:30080/v1/models | jq '.data[].id'
echo
curl -sS -o /tmp/infer_resp.json \
  -w '\nconnect=%{time_connect}s\nttfb=%{time_starttransfer}s\ne2e=%{time_total}s\n' \
  -X POST http://192.168.86.176:30080/v1/chat/completions \
  -H "X-Request-Id: request_id_1" \
  -H "X-Trace-Id: trace_id_1" \
  -H "X-Session-Id: session_id_1" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "messages": [{"role": "user", "content": "introduce new york city"}],
    "max_tokens": 8,
    "temperature": 0
  }'  
```

response
```
"Qwen/Qwen2.5-7B-Instruct"
"router-qwen2.5-7b-sft-v1.00"
"router-qwen2.5-7b-dpo-v1.00"


connect=0.014690s
ttfb=0.207991s
e2e=0.208242s

"Qwen/Qwen2.5-7B-Instruct"
"router-qwen2.5-7b-sft-v1.00"
"router-qwen2.5-7b-dpo-v1.00"


connect=0.006309s
ttfb=0.176060s
e2e=0.176304s
```


## test prompt size -> max-model-len

```bash
cat >/tmp/bench_infer_prompt.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

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
  "http://192.168.86.173:30080"
  "http://192.168.86.176:30080"
)

SIZES=(500 2000 4000 6000 8000)

SOURCE_URL="https://en.wikipedia.org/wiki/New_York_City"
INPUT_FILE=/tmp/vllm_infer_input.txt
PAYLOAD=/tmp/vllm_infer.json

TOTAL=100
CONCURRENCY=20
MODEL="Qwen/Qwen2.5-7B-Instruct"

echo "Fetching source..."
RAW=/tmp/wiki_raw.txt
curl -fsSL "$SOURCE_URL" \
  | lynx -dump -stdin \
  | iconv -f utf-8 -t utf-8 -c > "$RAW"

for SIZE in "${SIZES[@]}"; do
  echo ""
  echo "================ SIZE=${SIZE} ================="

  head -c "$SIZE" "$RAW" > "$INPUT_FILE"

  raw_chars=$(wc -c < "$INPUT_FILE" | tr -d ' ')
  tokens=$(( raw_chars / 4 ))

  python3 - <<PY
import json

with open("$INPUT_FILE", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

payload = {
    "model": "$MODEL",
    "messages": [{"role": "user", "content": text}],
    "max_tokens": 8,
    "temperature": 0,
}

with open("$PAYLOAD", "w", encoding="utf-8") as out:
    json.dump(payload, out)
PY

  for ENDPOINT in "${BACKENDS[@]}"; do
    tmpfile=$(mktemp)

    seq 1 $TOTAL | xargs -P $CONCURRENCY -I{} bash -c '
      curl -sS -o /dev/null \
        -w "%{http_code} %{time_starttransfer} %{time_total}\n" \
        -X POST "$1/v1/chat/completions" \
        -H "Content-Type: application/json" \
        --data-binary @"$2"
    ' _ "$ENDPOINT" "$PAYLOAD" > "$tmpfile"

    success=$(awk '$1 == 200 {c++} END {print c+0}' "$tmpfile")
    total=$(wc -l < "$tmpfile" | tr -d ' ')
    errors=$(( total - success ))

    p99_ttfb=$(awk '$1 == 200 {print $2}' "$tmpfile" | percentile_99)
    p99_e2e=$(awk '$1 == 200 {print $3}' "$tmpfile" | percentile_99)

    echo "backend=$ENDPOINT input_chars=$raw_chars approx_tokens=$tokens total=$total success=$success errors=$errors p99_ttfb=${p99_ttfb}s p99_e2e=${p99_e2e}s"

    rm -f "$tmpfile"
  done
done

rm -f "$INPUT_FILE" "$PAYLOAD" "$RAW"
echo "Done."
EOF

bash /tmp/bench_infer_prompt.sh
```

## test concurrent with small prompts -> max-num-seqs

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
  "http://192.168.86.173:30080"
  "http://192.168.86.176:30080"
)

MODEL="Qwen/Qwen2.5-7B-Instruct"
TOTAL_REQUESTS=500
INPUT_CHARS=300
MAX_TOKENS=64

INPUT_FILE=/tmp/vllm_infer_input.txt
PAYLOAD=/tmp/vllm_infer_small.json

SOURCE_URL="https://en.wikipedia.org/wiki/New_York_City"

curl -fsSL "$SOURCE_URL" | lynx -dump -stdin | iconv -f utf-8 -t utf-8 -c | head -c "$INPUT_CHARS" >"$INPUT_FILE"

raw_chars=$(wc -c <"$INPUT_FILE" | tr -d ' ')
approx_tokens=$(( raw_chars / 4 ))

python3 - <<'PY'
import json

with open("/tmp/vllm_infer_input.txt", "r", encoding="utf-8", errors="ignore") as f:
    payload = {
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "messages": [{"role": "user", "content": f.read()}],
        "max_tokens": 64,
        "temperature": 0,
    }

with open("/tmp/vllm_infer_small.json", "w", encoding="utf-8") as out:
    json.dump(payload, out)
PY

for CONCURRENCY in 2 10 20 40 60; do
  echo "CONCURRENCY=$CONCURRENCY"

  for ENDPOINT in "${BACKENDS[@]}"; do
    tmpfile=$(mktemp)

    seq 1 "$TOTAL_REQUESTS" | xargs -P "$CONCURRENCY" -I{} bash -c '
      curl -sS -o /dev/null \
        -w "%{http_code} %{time_starttransfer} %{time_total}\n" \
        -X POST "$1/v1/chat/completions" \
        -H "Content-Type: application/json" \
        --data-binary @"$2"
    ' _ "$ENDPOINT" "$PAYLOAD" >"$tmpfile"

    success=$(awk '$1 == "200" { c++ } END { print c + 0 }' "$tmpfile")
    total=$(wc -l <"$tmpfile" | tr -d " ")
    errors=$((total - success))

    p99_ttfb=$(awk '$1 == "200" { print $2 }' "$tmpfile" | percentile_99)
    p99_e2e=$(awk '$1 == "200" { print $3 }' "$tmpfile" | percentile_99)

    echo "backend=$ENDPOINT input_chars=$raw_chars approx_tokens=$approx_tokens max_tokens=$MAX_TOKENS concurrency=$CONCURRENCY total=$total success=$success errors=$errors p99_ttfb=${p99_ttfb}s p99_e2e=${p99_e2e}s"

    rm -f "$tmpfile"
  done

  echo ""
done

rm -f "$INPUT_FILE" "$PAYLOAD"
```

## test concurrent with large prompts -> max-num-seqs

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
  "http://192.168.86.173:30080"
  "http://192.168.86.176:30080"
)

MODEL="Qwen/Qwen2.5-7B-Instruct"
TOTAL_REQUESTS=500
INPUT_CHARS=8000
MAX_TOKENS=512

INPUT_FILE=/tmp/vllm_infer_input.txt
PAYLOAD=/tmp/vllm_infer_large.json

SOURCE_URL="https://en.wikipedia.org/wiki/New_York_City"

curl -fsSL "$SOURCE_URL" | lynx -dump -stdin | iconv -f utf-8 -t utf-8 -c | head -c "$INPUT_CHARS" >"$INPUT_FILE"

raw_chars=$(wc -c <"$INPUT_FILE" | tr -d ' ')
approx_tokens=$(( raw_chars / 4 ))

echo "input_chars=$raw_chars approx_tokens=$approx_tokens max_tokens=$MAX_TOKENS"

python3 - <<'PY'
import json

with open("/tmp/vllm_infer_input.txt", "r", encoding="utf-8", errors="ignore") as f:
    payload = {
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "messages": [{
            "role": "user",
            "content": (
                f.read()
                + "\n\nWrite a detailed 8-section travel guide for New York City including "
                "history, neighborhoods, transportation, food, attractions, itinerary, budget tips, and safety advice."
            ),
        }],
        "max_tokens": 512,
        "temperature": 0,
    }

with open("/tmp/vllm_infer_large.json", "w", encoding="utf-8") as out:
    json.dump(payload, out)
PY

for CONCURRENCY in 2 10 20 40 60; do
  echo "CONCURRENCY=$CONCURRENCY"

  for ENDPOINT in "${BACKENDS[@]}"; do
    tmpfile=$(mktemp)

    seq 1 "$TOTAL_REQUESTS" | xargs -P "$CONCURRENCY" -I{} bash -c '
      curl -sS -o /dev/null \
        -w "%{http_code} %{time_starttransfer} %{time_total}\n" \
        -X POST "$1/v1/chat/completions" \
        -H "Content-Type: application/json" \
        --data-binary @"$2"
    ' _ "$ENDPOINT" "$PAYLOAD" >"$tmpfile"

    success=$(awk '$1 == "200" { c++ } END { print c + 0 }' "$tmpfile")
    total=$(wc -l <"$tmpfile" | tr -d " ")
    errors=$((total - success))

    p99_ttfb=$(awk '$1 == "200" { print $2 }' "$tmpfile" | percentile_99)
    p99_e2e=$(awk '$1 == "200" { print $3 }' "$tmpfile" | percentile_99)

    echo "backend=$ENDPOINT input_chars=$raw_chars approx_tokens=$approx_tokens max_tokens=$MAX_TOKENS concurrency=$CONCURRENCY total=$total success=$success errors=$errors p99_ttfb=${p99_ttfb}s p99_e2e=${p99_e2e}s"

    rm -f "$tmpfile"
  done

  echo ""
done

rm -f "$INPUT_FILE" "$PAYLOAD"
```
