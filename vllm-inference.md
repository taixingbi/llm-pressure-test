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

SOURCE_URL="https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles=New_York_City&format=json"
INPUT_FILE=/tmp/vllm_infer_input.txt
PAYLOAD=/tmp/vllm_infer.json
RAW=/tmp/wiki_raw.txt

TOTAL=100
CONCURRENCY=20
MODEL="Qwen/Qwen2.5-7B-Instruct"

echo "Fetching source..."
curl -fsSL "$SOURCE_URL" | jq -r '.query.pages[].extract' > "$RAW"

for SIZE in "${SIZES[@]}"; do
  echo ""
  echo "================ SIZE=${SIZE} ================="

  head -c "$SIZE" "$RAW" > "$INPUT_FILE"

  raw_chars=$(wc -c < "$INPUT_FILE" | tr -d ' ')
  tokens=$(( raw_chars / 4 ))

  jq -n \
    --arg model "$MODEL" \
    --rawfile content "$INPUT_FILE" \
    '{
      model: $model,
      messages: [{role: "user", content: $content}],
      max_tokens: 8,
      temperature: 0
    }' > "$PAYLOAD"

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
```

```
================ SIZE=500 =================
backend=http://192.168.86.173:30080 input_chars=500 approx_tokens=125 total=100 success=100 errors=0 p99_ttfb=2.164795s p99_e2e=2.164878s
backend=http://192.168.86.176:30080 input_chars=500 approx_tokens=125 total=100 success=100 errors=0 p99_ttfb=3.131688s p99_e2e=3.131796s

================ SIZE=2000 =================
backend=http://192.168.86.173:30080 input_chars=2000 approx_tokens=500 total=100 success=100 errors=0 p99_ttfb=3.470500s p99_e2e=3.470599s
backend=http://192.168.86.176:30080 input_chars=2000 approx_tokens=500 total=100 success=100 errors=0 p99_ttfb=3.020592s p99_e2e=3.020702s

================ SIZE=4000 =================
backend=http://192.168.86.173:30080 input_chars=4000 approx_tokens=1000 total=100 success=100 errors=0 p99_ttfb=2.837704s p99_e2e=2.837750s
backend=http://192.168.86.176:30080 input_chars=4000 approx_tokens=1000 total=100 success=100 errors=0 p99_ttfb=2.606517s p99_e2e=2.606605s

================ SIZE=6000 =================
backend=http://192.168.86.173:30080 input_chars=6000 approx_tokens=1500 total=100 success=100 errors=0 p99_ttfb=2.779074s p99_e2e=2.779178s
backend=http://192.168.86.176:30080 input_chars=6000 approx_tokens=1500 total=100 success=100 errors=0 p99_ttfb=2.665286s p99_e2e=2.665384s

================ SIZE=8000 =================
backend=http://192.168.86.173:30080 input_chars=8000 approx_tokens=2000 total=100 success=100 errors=0 p99_ttfb=2.627962s p99_e2e=2.628062s
backend=http://192.168.86.176:30080 input_chars=8000 approx_tokens=2000 total=100 success=100 errors=0 p99_ttfb=2.698558s p99_e2e=2.698716s
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

SOURCE_URL="https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles=New_York_City&format=json"

curl -fsSL "$SOURCE_URL" | jq -r '.query.pages[].extract' | head -c "$INPUT_CHARS" >"$INPUT_FILE"

raw_chars=$(wc -c <"$INPUT_FILE" | tr -d ' ')
approx_tokens=$(( raw_chars / 4 ))

jq -n \
  --arg model "$MODEL" \
  --rawfile content "$INPUT_FILE" \
  '{
    model: $model,
    messages: [{role: "user", content: $content}],
    max_tokens: 64,
    temperature: 0
  }' >"$PAYLOAD"

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

SOURCE_URL="https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles=New_York_City&format=json"
SUFFIX=$'\n\nWrite a detailed 8-section travel guide for New York City including history, neighborhoods, transportation, food, attractions, itinerary, budget tips, and safety advice.'

curl -fsSL "$SOURCE_URL" | jq -r '.query.pages[].extract' | head -c "$INPUT_CHARS" >"$INPUT_FILE"

raw_chars=$(wc -c <"$INPUT_FILE" | tr -d ' ')
approx_tokens=$(( raw_chars / 4 ))

echo "input_chars=$raw_chars approx_tokens=$approx_tokens max_tokens=$MAX_TOKENS"

jq -n \
  --arg model "$MODEL" \
  --rawfile content "$INPUT_FILE" \
  --arg suffix "$SUFFIX" \
  '{
    model: $model,
    messages: [{role: "user", content: ($content + $suffix)}],
    max_tokens: 512,
    temperature: 0
  }' >"$PAYLOAD"

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
