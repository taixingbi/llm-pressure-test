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
| [README-gateway.md](README-gateway.md) | Gateway inference, embedding, reranker |
| [README-direct-vllm.md](README-direct-vllm.md) | Direct gpu-node inference, embedding, reranker |
| [README-rag.md](README-rag.md) | RAG query (`/v1/rag/query`) |
| This file | Setup, orchestrator, shared config |

## Layout

| File | User class(es) | Target |
|------|----------------|--------|
| `workload_inference.py` | `WorkloadInferenceUser` (abstract) | shared chat workload |
| `workload_embedding.py` | `WorkloadEmbeddingUser` (abstract) | shared embedding workload |
| `workload_reranker.py` | `WorkloadRerankerUser` (abstract) | shared reranker workload |
| `workload_rag.py` | `WorkloadRagUser` (abstract) | shared RAG query workload |
| `gateway_inference.py` | `GatewayInferenceUser` | `GATEWAY_INFER` |
| `gateway_embedding.py` | `GatewayEmbeddingUser` | `GATEWAY_EMBED` |
| `gateway_reranker.py` | `GatewayRerankerUser` | `GATEWAY_RERANK` |
| `vllm_inference.py` | `VllmInferenceNode1`, `VllmInferenceNode2` | direct GPU inference |
| `vllm_embedding.py` | `VllmEmbeddingNode1`, `VllmEmbeddingNode2` | direct GPU embedding |
| `vllm_reranker.py` | `VllmRerankerNode1`, `VllmRerankerNode2` | direct GPU reranker |
| `gateway_reranker.py` | `GatewayRerankerUser` | `/v1/rerank` |
| `rag_query.py` | `RagQueryUser` | `/v1/rag/query` |
| `orchestrator.py` | `OrchestratorUser` | `/orchestrator/stream-answer` |

Shared modules:

- `settings.py` — host URLs and model names (env overrides)
- `helpers.py` — payload builders, trace headers, stream drain

## Smoke test before Locust

Gateway: [README-gateway.md](README-gateway.md) → `../smoke-test/gateway-*.md`

Direct nodes: [README-direct-vllm.md](README-direct-vllm.md) → `../smoke-test/vllm-*.md`

RAG: [README-rag.md](README-rag.md) → `../smoke-test/rag-query.md`

## Run (web UI)

### Gateway

Inference, embedding, reranker: [README-gateway.md](README-gateway.md).

### Direct vLLM nodes

Inference, embedding, reranker on gpu-node-1 / gpu-node-2: [README-direct-vllm.md](README-direct-vllm.md).

### RAG query (`:30183`)

[README-rag.md](README-rag.md)

### Orchestrator

```bash
locust -f orchestrator.py
```

Open http://localhost:8089 to adjust users/spawn rate interactively.

## Run (headless)

Gateway: [README-gateway.md](README-gateway.md).

Direct vLLM: [README-direct-vllm.md](README-direct-vllm.md).

RAG: [README-rag.md](README-rag.md).

```bash
locust -f orchestrator.py --headless -u 10 -r 5 -t 5m
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

locust -f vllm_inference.py VllmInferenceNode1 --web-port 8090 --host http://192.168.86.173:30080 --users 4 --spawn-rate 1
locust -f gateway_inference.py --web-port 8090 --users 1 --spawn-rate 1
```

Gateway troubleshooting: [README-gateway.md](README-gateway.md#troubleshooting).

Direct-node troubleshooting: [README-direct-vllm.md](README-direct-vllm.md#troubleshooting).

## Scenarios per service

**Gateway** — [README-gateway.md](README-gateway.md).

**Direct vLLM** — [README-direct-vllm.md](README-direct-vllm.md).

**RAG query** — [README-rag.md](README-rag.md).

**Orchestrator** — streaming `stream-answer`; response body is fully read before marking success.

## Notes

- Requests include `X-Request-Id`, `X-Trace-Id`, and `X-Session-Id` for traceability under load.
- Non-200 responses are recorded as failures in Locust stats.
- Streaming endpoints wait for the full body (or timeout) so latency reflects end-to-end completion.
