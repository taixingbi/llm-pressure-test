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
curl -sS -o /tmp/infer_resp_173.json \
  -w '\nconnect=%{time_connect}s\nttfb=%{time_starttransfer}s\ne2e=%{time_total}s\n' \
  -X POST http://192.168.86.173:30080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "messages": [{"role": "user", "content": "introduce new york city"}],
    "max_tokens": 256,
    "temperature": 0
  }'

echo "=== response 173 ==="
jq . /tmp/infer_resp_173.json
jq -r '.choices[0].message.content' /tmp/infer_resp_173.json  
```

```bash
curl -sS -o /tmp/infer_resp_176.json \
  -w '\nconnect=%{time_connect}s\nttfb=%{time_starttransfer}s\ne2e=%{time_total}s\n' \
  -X POST http://192.168.86.176:30080/v1/chat/completions \
  -H "X-Request-Id: request_id_1" \
  -H "X-Trace-Id: trace_id_1" \
  -H "X-Session-Id: session_id_1" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "messages": [{"role": "user", "content": "introduce new york city"}],
    "max_tokens": 256,
    "temperature": 0
  }'

echo "=== response 176 ==="
jq . /tmp/infer_resp_176.json
jq -r '.choices[0].message.content' /tmp/infer_resp_176.json
```

Example timing (gpu-node-2, `max_tokens=256`):

```
connect=0.111035s
ttfb=5.418016s
e2e=5.418384s
```

`finish_reason=length` with `completion_tokens=256` is expected when generation hits `max_tokens`.