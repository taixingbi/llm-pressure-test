# Locust load tests

Locust scenarios for the services documented in the parent repo (`vllm-*.md`, `gateway-*.md`, `rag-query.md`, `orchestrator.md`).

## Setup

```bash
cd locust
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run all commands from the `locust/` directory so `settings` and `helpers` imports resolve.

## Docs

| Doc | Coverage |
|-----|----------|
| [README-direct-vllm.md](README-direct-vllm.md) | Direct gpu-node inference, embedding, reranker |
| This file | Gateway, RAG, orchestrator, shared config |

## Layout

| File | User class(es) | Target |
|------|----------------|--------|
| `locustfile.py` | `GatewayInferenceUser` | gateway inference (default entry) |
| `inference_workload.py` | `InferenceWorkloadUser` (abstract) | shared chat workload |
| `gateway_inference.py` | `GatewayInferenceUser` | `GATEWAY_INFER` |
| `vllm_inference.py` | `VllmInferenceNode1`, `VllmInferenceNode2` | direct GPU nodes |
| `vllm_embedding.py` | `VllmEmbeddingNode1`, `VllmEmbeddingNode2` | `/v1/embeddings` |
| `vllm_reranker.py` | `VllmRerankerNode1`, `VllmRerankerNode2` | `/v1/rerank` |
| `gateway_embedding.py` | `GatewayEmbeddingUser` | `/v1/embeddings` |
| `gateway_reranker.py` | `GatewayRerankerUser` | `/v1/rerank` |
| `rag_query.py` | `RagQueryUser` | `/v1/rag/query` |
| `orchestrator.py` | `OrchestratorUser` | `/orchestrator/stream-answer` |

Shared modules:

- `settings.py` — host URLs and model names (env overrides)
- `helpers.py` — payload builders, trace headers, stream drain

## Smoke test before Locust (gateway)

```bash
curl -sS -o /dev/null \
  -w 'status=%{http_code} ttfb=%{time_starttransfer}s e2e=%{time_total}s\n' \
  -X POST http://192.168.86.179:30180/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "messages": [{"role": "user", "content": "introduce new york city"}],
    "max_tokens": 64,
    "temperature": 0
  }'
```

Direct-node smoke tests: [README-direct-vllm.md](README-direct-vllm.md).

## Run (web UI)

### Gateway inference

```bash
locust -f locustfile.py --users 1 --spawn-rate 1
```

Ramp only after 1 user is stable (0% failures, latency not stuck at ~30s):

```bash
locust -f locustfile.py --users 2 --spawn-rate 1
locust -f locustfile.py --users 4 --spawn-rate 1
```

### Direct vLLM nodes

Inference, embedding, and reranker on gpu-node-1 / gpu-node-2: see [README-direct-vllm.md](README-direct-vllm.md).

### Other services

```bash
locust -f rag_query.py
locust -f orchestrator.py
```

Open http://localhost:8089 to adjust users/spawn rate interactively.

## Run (headless)

Gateway inference:

```bash
locust -f locustfile.py --headless --users 1 --spawn-rate 1 -t 2m
```

Other services:

```bash
locust -f rag_query.py --headless -u 20 -r 10 -t 2m
locust -f orchestrator.py --headless -u 10 -r 5 -t 5m
```

Direct vLLM headless runs: [README-direct-vllm.md](README-direct-vllm.md).

Export CSV:

```bash
locust -f locustfile.py --headless -u 1 -r 1 -t 2m --csv=results/gateway-infer
```

## Configuration

Defaults match the IPs/ports in the markdown docs. Override with env vars:

```bash
export VLLM_INFER_NODE1=http://192.168.86.173:30080
export VLLM_INFER_NODE2=http://192.168.86.176:30080
export VLLM_EMBED_NODE1=http://192.168.86.173:30081
export VLLM_EMBED_NODE2=http://192.168.86.176:30081
export VLLM_RERANK_NODE1=http://192.168.86.173:30082
export VLLM_RERANK_NODE2=http://192.168.86.176:30082

export GATEWAY_INFER=http://192.168.86.179:30180
export GATEWAY_EMBED=http://192.168.86.179:30181
export GATEWAY_RERANK=http://192.168.86.179:30182

export RAG_URL=http://192.168.86.179:30183
export ORCH_URL=http://192.168.86.179:30184

export INFER_MODEL=Qwen/Qwen2.5-7B-Instruct
export EMBED_MODEL=BAAI/bge-m3
export RERANK_MODEL=BAAI/bge-reranker-v2-m3
export RAG_COLLECTION=taixing_knowledge
```

## Troubleshooting

### Port 8089 already in use

```bash
lsof -nP -iTCP:8089 -sTCP:LISTEN
kill -9 <PID>
```

Or use another UI port:

```bash
locust -f locustfile.py --web-port 8090 --users 1 --spawn-rate 1
```

### All requests fail at ~30s with ~56-byte body

Typical with gateway + `--max-num-seqs 1` + too many users. Drop to `--users 1` and check the **Failures** tab for `status=502/504: ...`.

Compare gateway vs direct node: [README-direct-vllm.md](README-direct-vllm.md#troubleshooting).

### `No tasks defined on GatewayInferenceUser`

Tasks must live on an `HttpUser` subclass. Use the current `InferenceWorkloadUser` base class pattern; do not put `@task` on a plain mixin.

## Scenarios per service

**Gateway inference** — weighted mix: small 64 (6), medium 128 (2), stream 256 (1). See `locustfile.py`.

**Direct vLLM inference / embedding / reranker** — see [README-direct-vllm.md](README-direct-vllm.md).

**Gateway embedding** — small input (300 chars), large input (8000 chars).

**Gateway reranker** — short docs (2 sentences), 512-char doc + short second doc.

**RAG query** — `what is taixing visa` with unique `request_id` / `session_id` per request.

**Orchestrator** — streaming `stream-answer`; response body is fully read before marking success.

## Notes

- Requests include `X-Request-Id`, `X-Trace-Id`, and `X-Session-Id` for traceability under load.
- Non-200 responses are recorded as failures in Locust stats.
- Streaming endpoints wait for the full body (or timeout) so latency reflects end-to-end completion.
