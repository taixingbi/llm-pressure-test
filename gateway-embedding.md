## gateway-embedding

```bash
curl -sS \
  -w '\nconnect=%{time_connect}s\nttfb=%{time_starttransfer}s\ne2e=%{time_total}s\n' \
  -X POST http://192.168.86.179:30181/v1/embeddings \
  -H "X-Request-Id: request_id_1" \
  -H "X-Trace-Id: trace_id_1" \
  -H "X-Session-Id: session_id_1" \
  -H "Content-Type: application/json" \
  -d '{"model":"BAAI/bge-m3","input":"hello world"}'
```

#### test concurrent with small tokens -> max-num-seqs
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
  "http://192.168.86.173:8001"
  "http://192.168.86.176:8001"
  "http://192.168.86.179:30181"
)

SOURCE_URL="https://en.wikipedia.org/wiki/New_York_City"
TOTAL_REQUESTS=500
CONCURRENCY=80
INPUT_CHARS=300

INPUT_FILE=/tmp/vllm_embed_input.txt
PAYLOAD=/tmp/vllm_embed.json

echo "NOTE:"
echo "- 192.168.86.173:8001 and 192.168.86.176:8001 are direct backend tests."
echo "- 192.168.86.179:30181 is the gateway test."
echo "- Gateway results are not perfectly apples-to-apples with direct backend results."
echo "- The JSON shape is the same, but the gateway path adds proxy/routing overhead."
echo "- The gateway requests below also include X-Request-Id / X-Trace-Id / X-Session-Id headers."

curl -fsSL "$SOURCE_URL" \
  | lynx -dump -stdin \
  | iconv -f utf-8 -t utf-8 -c \
  | head -c "$INPUT_CHARS" > "$INPUT_FILE"

raw_chars=$(wc -c <"$INPUT_FILE" | tr -d ' ')
approx_tokens=$(( raw_chars / 4 ))

python3 - <<'PY'
import json
with open("/tmp/vllm_embed_input.txt", "r", encoding="utf-8", errors="ignore") as f:
    payload = {"model": "BAAI/bge-m3", "input": f.read()}
with open("/tmp/vllm_embed.json", "w", encoding="utf-8") as out:
    json.dump(payload, out)
PY

for ENDPOINT in "${BACKENDS[@]}"; do
  tmpfile=$(mktemp)

  if [[ "$ENDPOINT" == "http://192.168.86.179:30181" ]]; then
    target_type="gateway"

    seq 1 "$TOTAL_REQUESTS" | xargs -P "$CONCURRENCY" -I{} bash -c '
      i="$1"
      endpoint="$2"
      payload="$3"

      curl -sS -o /dev/null \
        -w "%{http_code} %{time_connect} %{time_starttransfer} %{time_total}\n" \
        -X POST "$endpoint/v1/embeddings" \
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
        -X POST "$endpoint/v1/embeddings" \
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

  echo "backend=$ENDPOINT type=$target_type input_chars=$raw_chars approx_tokens=$approx_tokens total=$total success=$success errors=$errors total_e2e=${total_e2e}s avg_e2e=${avg_e2e}s p99_connect=${p99_connect}s p99_ttfb=${p99_ttfb}s p99_e2e=${p99_e2e}s"

  rm -f "$tmpfile"
done

rm -f "$INPUT_FILE" "$PAYLOAD"
```

```
backend=http://192.168.86.173:8001 type=direct input_chars=300 approx_tokens=75 total=500 success=500 errors=0 total_e2e=47.660946s avg_e2e=0.095322s p99_connect=0.055897s p99_ttfb=0.128292s p99_e2e=0.167418s
backend=http://192.168.86.176:8001 type=direct input_chars=300 approx_tokens=75 total=500 success=500 errors=0 total_e2e=166.241936s avg_e2e=0.332484s p99_connect=0.205537s p99_ttfb=0.408364s p99_e2e=0.650701s
backend=http://192.168.86.179:30181 type=gateway input_chars=300 approx_tokens=75 total=500 success=500 errors=0 total_e2e=411.943362s avg_e2e=0.823887s p99_connect=0.460306s p99_ttfb=1.219513s p99_e2e=2.157005s
```

test concurrent with large tokens -> max-num-seqs

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
  "http://192.168.86.173:8001"
  "http://192.168.86.176:8001"
  "http://192.168.86.179:30181"
)

SOURCE_URL="https://en.wikipedia.org/wiki/New_York_City"
TOTAL_REQUESTS=500
CONCURRENCY=80
INPUT_CHARS=8000

INPUT_FILE=/tmp/vllm_embed_input.txt
PAYLOAD=/tmp/vllm_embed.json

echo "NOTE:"
echo "- 192.168.86.173:8001 and 192.168.86.176:8001 are direct backend tests."
echo "- 192.168.86.179:30181 is the gateway test."
echo "- Gateway results are not perfectly apples-to-apples with direct backend results."
echo "- The gateway path adds proxy/routing overhead."
echo "- Gateway requests include X-Request-Id / X-Trace-Id / X-Session-Id headers."

curl -fsSL "$SOURCE_URL" \
  | lynx -dump -stdin \
  | iconv -f utf-8 -t utf-8 -c \
  | head -c "$INPUT_CHARS" > "$INPUT_FILE"

raw_chars=$(wc -c < "$INPUT_FILE" | tr -d ' ')
approx_tokens=$(( raw_chars / 4 ))

echo "input_chars=$raw_chars approx_tokens=$approx_tokens"

python3 - <<'PY'
import json

with open("/tmp/vllm_embed_input.txt", "r", encoding="utf-8", errors="ignore") as f:
    payload = {"model": "BAAI/bge-m3", "input": f.read()}

with open("/tmp/vllm_embed.json", "w", encoding="utf-8") as out:
    json.dump(payload, out)
PY

for ENDPOINT in "${BACKENDS[@]}"; do
  tmpfile=$(mktemp)

  if [[ "$ENDPOINT" == "http://192.168.86.179:30181" ]]; then
    target_type="gateway"

    seq 1 "$TOTAL_REQUESTS" | xargs -P "$CONCURRENCY" -I{} bash -c '
      i="$1"
      endpoint="$2"
      payload="$3"

      curl -sS -o /dev/null \
        -w "%{http_code} %{time_connect} %{time_starttransfer} %{time_total}\n" \
        -X POST "$endpoint/v1/embeddings" \
        -H "X-Request-Id: request_id_$i" \
        -H "X-Trace-Id: trace_id_$i" \
        -H "X-Session-Id: session_id_$i" \
        -H "Content-Type: application/json" \
        --data-binary @"$payload"
    ' _ {} "$ENDPOINT" "$PAYLOAD" > "$tmpfile" 2>/dev/null
  else
    target_type="direct"

    seq 1 "$TOTAL_REQUESTS" | xargs -P "$CONCURRENCY" -I{} bash -c '
      endpoint="$1"
      payload="$2"

      curl -sS -o /dev/null \
        -w "%{http_code} %{time_connect} %{time_starttransfer} %{time_total}\n" \
        -X POST "$endpoint/v1/embeddings" \
        -H "Content-Type: application/json" \
        --data-binary @"$payload"
    ' _ "$ENDPOINT" "$PAYLOAD" > "$tmpfile" 2>/dev/null
  fi

  success=$(awk '$1 == "200" { c++ } END { print c + 0 }' "$tmpfile")
  total=$(wc -l < "$tmpfile" | tr -d ' ')
  errors=$((total - success))

  p99_connect=$(awk '$1 == "200" { print $2 }' "$tmpfile" | percentile_99)
  p99_ttfb=$(awk '$1 == "200" { print $3 }' "$tmpfile" | percentile_99)
  p99_e2e=$(awk '$1 == "200" { print $4 }' "$tmpfile" | percentile_99)

  total_e2e=$(awk '$1 == "200" { sum += $4 } END { printf "%.6f", sum + 0 }' "$tmpfile")
  avg_e2e=$(awk '$1 == "200" { sum += $4; c++ } END { if (c == 0) print "NA"; else printf "%.6f", sum / c }' "$tmpfile")

  echo "backend=$ENDPOINT type=$target_type input_chars=$raw_chars approx_tokens=$approx_tokens total=$total success=$success errors=$errors total_e2e=${total_e2e}s avg_e2e=${avg_e2e}s p99_connect=${p99_connect}s p99_ttfb=${p99_ttfb}s p99_e2e=${p99_e2e}s"

  rm -f "$tmpfile"
done

rm -f "$INPUT_FILE" "$PAYLOAD"
```


```
input_chars=8000 approx_tokens=2000
backend=http://192.168.86.173:8001 type=direct input_chars=8000 approx_tokens=2000 total=500 success=500 errors=0 total_e2e=1285.583684s avg_e2e=2.571167s p99_connect=0.021638s p99_ttfb=2.800071s p99_e2e=2.811892s
backend=http://192.168.86.176:8001 type=direct input_chars=8000 approx_tokens=2000 total=500 success=500 errors=0 total_e2e=1265.091164s avg_e2e=2.530182s p99_connect=0.024145s p99_ttfb=2.753359s p99_e2e=2.764730s
backend=http://192.168.86.179:30181 type=gateway input_chars=8000 approx_tokens=2000 total=500 success=500 errors=0 total_e2e=644.332029s avg_e2e=1.288664s p99_connect=0.218935s p99_ttfb=1.406733s p99_e2e=1.485793s
```


#### test tokens -> max-model-len

```bash
cat >/tmp/bench_embed.sh <<'EOF'
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
  "http://192.168.86.173:8001"
  "http://192.168.86.176:8001"
  "http://192.168.86.179:30181"
)

SIZES=(5000 10000 13000 15000 30000)

SOURCE_URL="https://en.wikipedia.org/wiki/New_York_City"
INPUT_FILE=/tmp/vllm_embed_input.txt
PAYLOAD=/tmp/vllm_embed.json

TOTAL=100
CONCURRENCY=20

echo "Fetching source..."
RAW=/tmp/wiki_raw.txt
curl -fsSL "$SOURCE_URL" \
  | lynx -dump -stdin \
  | iconv -f utf-8 -t utf-8 -c > "$RAW"

echo ""
echo "NOTE:"
echo "- 192.168.86.173:8001 and 192.168.86.176:8001 are direct backend tests."
echo "- 192.168.86.179:30181 is the gateway test."
echo "- Gateway results are NOT perfectly apples-to-apples with direct backend results."
echo "- The gateway path may add routing / queue / proxy overhead."
echo "- In your single curl example, the gateway request also includes X-Request-Id / X-Trace-Id / X-Session-Id headers."

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

payload = {"model": "BAAI/bge-m3", "input": text}

with open("$PAYLOAD", "w", encoding="utf-8") as out:
    json.dump(payload, out)
PY

  for ENDPOINT in "${BACKENDS[@]}"; do
    tmpfile=$(mktemp)

    if [[ "$ENDPOINT" == "http://192.168.86.179:30181" ]]; then
      target_type="gateway"
      seq 1 $TOTAL | xargs -P $CONCURRENCY -I{} bash -c '
        i="$1"
        endpoint="$2"
        payload="$3"

        curl -sS -o /dev/null \
          -w "%{http_code} %{time_connect} %{time_starttransfer} %{time_total}\n" \
          -X POST "$endpoint/v1/embeddings" \
          -H "X-Request-Id: request_id_$i" \
          -H "X-Trace-Id: trace_id_$i" \
          -H "X-Session-Id: session_id_$i" \
          -H "Content-Type: application/json" \
          --data-binary @"$payload"
      ' _ {} "$ENDPOINT" "$PAYLOAD" > "$tmpfile"
    else
      target_type="direct"
      seq 1 $TOTAL | xargs -P $CONCURRENCY -I{} bash -c '
        endpoint="$1"
        payload="$2"

        curl -sS -o /dev/null \
          -w "%{http_code} %{time_connect} %{time_starttransfer} %{time_total}\n" \
          -X POST "$endpoint/v1/embeddings" \
          -H "Content-Type: application/json" \
          --data-binary @"$payload"
      ' _ "$ENDPOINT" "$PAYLOAD" > "$tmpfile"
    fi

    success=$(awk '$1 == 200 {c++} END {print c+0}' "$tmpfile")
    total=$(wc -l < "$tmpfile" | tr -d ' ')
    errors=$(( total - success ))

    p99_connect=$(awk '$1 == 200 {print $2}' "$tmpfile" | percentile_99)
    p99_ttfb=$(awk '$1 == 200 {print $3}' "$tmpfile" | percentile_99)
    p99_e2e=$(awk '$1 == 200 {print $4}' "$tmpfile" | percentile_99)

    echo "backend=$ENDPOINT type=$target_type input_chars=$raw_chars approx_tokens=$tokens total=$total success=$success errors=$errors p99_connect=${p99_connect}s p99_ttfb=${p99_ttfb}s p99_e2e=${p99_e2e}s"

    rm -f "$tmpfile"
  done
done

rm -f "$INPUT_FILE" "$PAYLOAD" "$RAW"
echo "Done."
EOF

bash /tmp/bench_embed.sh
```



```
================ SIZE=5000 =================
backend=http://192.168.86.173:8001 type=direct input_chars=5000 approx_tokens=1250 total=100 success=100 errors=0 p99_connect=0.081760s p99_ttfb=0.450877s p99_e2e=0.504024s
backend=http://192.168.86.176:8001 type=direct input_chars=5000 approx_tokens=1250 total=100 success=100 errors=0 p99_connect=0.114259s p99_ttfb=0.503978s p99_e2e=0.513920s
backend=http://192.168.86.179:30181 type=gateway input_chars=5000 approx_tokens=1250 total=100 success=100 errors=0 p99_connect=0.100759s p99_ttfb=0.294396s p99_e2e=0.364988s

================ SIZE=10000 =================
backend=http://192.168.86.173:8001 type=direct input_chars=10000 approx_tokens=2500 total=100 success=100 errors=0 p99_connect=0.076935s p99_ttfb=1.015813s p99_e2e=1.025489s
backend=http://192.168.86.176:8001 type=direct input_chars=10000 approx_tokens=2500 total=100 success=100 errors=0 p99_connect=0.022666s p99_ttfb=0.965434s p99_e2e=0.990459s
backend=http://192.168.86.179:30181 type=gateway input_chars=10000 approx_tokens=2500 total=100 success=100 errors=0 p99_connect=0.120890s p99_ttfb=0.568452s p99_e2e=0.608738s

================ SIZE=13000 =================
backend=http://192.168.86.173:8001 type=direct input_chars=13000 approx_tokens=3250 total=100 success=0 errors=100 p99_connect=NAs p99_ttfb=NAs p99_e2e=NAs
backend=http://192.168.86.176:8001 type=direct input_chars=13000 approx_tokens=3250 total=100 success=0 errors=100 p99_connect=NAs p99_ttfb=NAs p99_e2e=NAs
backend=http://192.168.86.179:30181 type=gateway input_chars=13000 approx_tokens=3250 total=100 success=0 errors=100 p99_connect=NAs p99_ttfb=NAs p99_e2e=NAs

================ SIZE=15000 =================
backend=http://192.168.86.173:8001 type=direct input_chars=15000 approx_tokens=3750 total=100 success=0 errors=100 p99_connect=NAs p99_ttfb=NAs p99_e2e=NAs
backend=http://192.168.86.176:8001 type=direct input_chars=15000 approx_tokens=3750 total=100 success=0 errors=100 p99_connect=NAs p99_ttfb=NAs p99_e2e=NAs
backend=http://192.168.86.179:30181 type=gateway input_chars=15000 approx_tokens=3750 total=100 success=0 errors=100 p99_connect=NAs p99_ttfb=NAs p99_e2e=NAs

================ SIZE=30000 =================
backend=http://192.168.86.173:8001 type=direct input_chars=30000 approx_tokens=7500 total=100 success=0 errors=100 p99_connect=NAs p99_ttfb=NAs p99_e2e=NAs
backend=http://192.168.86.176:8001 type=direct input_chars=30000 approx_tokens=7500 total=100 success=0 errors=100 p99_connect=NAs p99_ttfb=NAs p99_e2e=NAs
backend=http://192.168.86.179:30181 type=gateway input_chars=30000 approx_tokens=7500 total=100 success=0 errors=100 p99_connect=NAs p99_ttfb=NAs p99_e2e=NAs
```

