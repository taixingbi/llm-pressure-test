# Locust load tests

Locust scenarios for the services documented in the parent repo (`vllm-*.md`, `gateway-*.md`, `rag-query.md`, `orchestrator.md`). Each file mirrors the curl benchmarks: small/large payloads, concurrency sweeps, distinct trace IDs, and full stream draining where applicable.

## Setup

```bash
cd locust
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Layout

| File | User class(es) | Endpoint(s) |
|------|----------------|-------------|
| `locustfile.py` | `GatewayInferenceUser` | `/v1/chat/completions` (default entry) |
| `vllm_inference.py` | `VllmInferenceNode1`, `VllmInferenceNode2` | `/v1/chat/completions` |
| `vllm_embedding.py` | `VllmEmbeddingNode1`, `VllmEmbeddingNode2` | `/v1/embeddings` |
| `vllm_reranker.py` | `VllmRerankerNode1`, `VllmRerankerNode2` | `/v1/rerank` |
| `gateway_inference.py` | `GatewayInferenceUser` | `/v1/chat/completions` (incl. stream) |
| `gateway_embedding.py` | `GatewayEmbeddingUser` | `/v1/embeddings` |
| `gateway_reranker.py` | `GatewayRerankerUser` | `/v1/rerank` |
| `rag_query.py` | `RagQueryUser` | `/v1/rag/query` |
| `orchestrator.py` | `OrchestratorUser` | `/orchestrator/stream-answer` |

Shared modules:

- `settings.py` — host URLs and model names (env overrides)
- `helpers.py` — payload builders, trace headers, stream drain

## Run (web UI)

Start with the light gateway inference workload (`max_tokens` 64 / 128 / 256 only):

```bash
# max-num-seqs 1: start with a single user
locust -f locustfile.py --users 1 --spawn-rate 1

# ramp only after 1 user is stable (0% failures, latency not ~30s)
locust -f locustfile.py --users 2 --spawn-rate 1
locust -f locustfile.py --users 4 --spawn-rate 1
```

Direct vLLM nodes (same workload, both GPUs):

```bash
locust -f vllm_inference.py --users 1 --spawn-rate 1
locust -f vllm_inference.py VllmInferenceNode1 --users 1 --spawn-rate 1
```

Other services:

```bash
locust -f rag_query.py
locust -f orchestrator.py
```

Open http://localhost:8089 to adjust users/spawn rate interactively.

### vLLM config note

Tuned for `--max-model-len 2048` and `--max-num-seqs 1`. Avoid flooding with `max_tokens=512` requests — they queue badly at this setting. Re-introduce heavier generation tests after raising to `--max-num-seqs 4` or higher.

If every request fails at **~30s** with a tiny response body (~55 bytes), the gateway upstream timed out while extra users queued behind the single vLLM sequence slot. Drop to `--users 1` and confirm a single curl smoke test succeeds first.

If direct-node curl is healthy (~5s for `max_tokens=256`) but gateway Locust fails, isolate the backend:

```bash
locust -f vllm_inference.py VllmInferenceNode2 --users 1 --spawn-rate 1
```

Stable direct-node results under load point at gateway queueing/timeout, not vLLM inference itself.

## Run (headless)

Matches the concurrency-sweep style from the bash benchmarks:

```bash
# 20 users, spawn 10/s, run 2 minutes
locust -f rag_query.py --headless -u 20 -r 10 -t 2m

locust -f orchestrator.py --headless -u 10 -r 5 -t 5m

locust -f vllm_inference.py VllmInferenceNode1 --headless -u 20 -r 10 -t 2m
```

Export results:

```bash
locust -f rag_query.py --headless -u 20 -r 10 -t 2m --csv=results/rag
```

## Configuration

Defaults match the IPs/ports in the markdown docs. Override with env vars:

```bash
export VLLM_INFER_NODE1=http://192.168.86.173:30080
export VLLM_INFER_NODE2=http://192.168.86.176:30080
export VLLM_EMBED_NODE1=http://192.168.86.173:8001
export VLLM_EMBED_NODE2=http://192.168.86.176:8001
export VLLM_RERANK_NODE1=http://192.168.86.173:8002
export VLLM_RERANK_NODE2=http://192.168.86.176:8002

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

## Scenarios per service

**Gateway inference / vLLM inference** (`locustfile.py`, `gateway_inference.py`, `vllm_inference.py`) — weighted mix: small (`max_tokens=64`, weight 6), medium (`max_tokens=128`, weight 2), stream (`max_tokens=256`, weight 1).

**vLLM embedding / gateway embedding** — small input (300 chars), large input (8000 chars).

**vLLM reranker / gateway reranker** — short docs (2 sentences), long doc (~6000 chars + short second doc).

**RAG query** — `what is taixing visa` with unique `request_id` / `session_id` per request.

**Orchestrator** — streaming `stream-answer`; response body is fully read before marking success.

## Notes

- Requests include `X-Request-Id`, `X-Trace-Id`, and `X-Session-Id` for traceability under load.
- Non-200 responses are recorded as failures in Locust stats.
- Streaming endpoints wait for the full body (or timeout) so latency reflects end-to-end completion.
- Run from the `locust/` directory so `settings` and `helpers` imports resolve.
