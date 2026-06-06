# Direct vLLM nodes (Locust)

Load tests for inference, embedding, and reranker on gpu-node-1 / gpu-node-2. See [README.md](README.md) for setup and shared configuration.

Parent curl benchmarks: `vllm-inference.md`, `vllm-embedding.md`, `vllm-reranker.md`.

Smoke tests (run before Locust): `../smoke-test/vllm-inference.md`, `vllm-embedding.md`, `vllm-reranker.md`. Gateway: [README-gateway.md](README-gateway.md).

## Locust files

| Service | File | User classes | Port |
|---------|------|--------------|------|
| Inference | `vllm_inference.py` | `VllmInferenceNode1`, `VllmInferenceNode2` | 30080 |
| Embedding | `vllm_embedding.py` | `VllmEmbeddingNode1`, `VllmEmbeddingNode2` | 30081 |
| Reranker | `vllm_reranker.py` | `VllmRerankerNode1`, `VllmRerankerNode2` | 30082 |

Shared workloads: `workload_inference.py`, `workload_embedding.py`, `workload_reranker.py`.

## Inference workload

Tuned for current vLLM chat config:

```
--max-model-len 2048
--max-num-seqs 8
```

Task mix (`workload_inference.py`):

| Task | max_tokens | Weight | Share | Timeout |
|------|------------|--------|-------|---------|
| small | 64 | 6 | 60% | 60s |
| medium | 128 | 2 | 20% | 90s |
| stream | 256 | 1 | 10% | 120s |
| long | 512 | 1 | 10% | 180s |

Streaming tasks fully drain SSE (`helpers.drain_stream`) and fail if no chunks arrive.

`wait_time` is `1–2s` between tasks.

### Test matrix

| Users | Meaning |
|-------|---------|
| 4 | Under capacity (baseline) |
| 8 | Matches `max-num-seqs` |
| 16 | 2× queue pressure |
| 24 | 3× queue pressure |
| 32 | Stress / timeout test |

**Pass condition:** `fail = 0`, p95 &lt; 10s, p99 &lt; 20s.

**Product/dev bar:** 8 users stable = good; 16 users stable = very good; 24+ = stress only.

## Embedding workload

Task mix (`workload_embedding.py`):

| Task | Input | Weight | Timeout |
|------|-------|--------|---------|
| small | 300 chars | 3 | 30s |
| large | 8000 chars | 1 | 120s |

Responses must include non-empty `data` (embedding vectors).

## Reranker workload

| Task | Payload | Weight |
|------|---------|--------|
| short | 2 short documents | 3 |
| 512 | 512-char doc + 1 short doc | 1 |

512 chars keeps query + documents within reranker `max-model-len 2048`. A ~6000-char doc returns fast 400s.

## Run (web UI)

Pick one node and pass `--host` explicitly so the web UI does not send traffic to the wrong target. Start at **4 users**, spawn rate **1**, then ramp **8 → 16 → 24 → 32**.

### Inference (`:30080`)

```bash
# gpu-node-1
locust -f vllm_inference.py VllmInferenceNode1 \
  --host http://192.168.86.173:30080 \
  --users 4 --spawn-rate 1
```

Ramp after each level is stable (gpu-node-1):

```bash
locust -f vllm_inference.py VllmInferenceNode1 \
  --host http://192.168.86.173:30080 \
  --users 8 --spawn-rate 1

locust -f vllm_inference.py VllmInferenceNode1 \
  --host http://192.168.86.173:30080 \
  --users 16 --spawn-rate 1

locust -f vllm_inference.py VllmInferenceNode1 \
  --host http://192.168.86.173:30080 \
  --users 24 --spawn-rate 1

locust -f vllm_inference.py VllmInferenceNode1 \
  --host http://192.168.86.173:30080 \
  --users 32 --spawn-rate 1
```

gpu-node-2 (same matrix, swap host and user class):

```bash
locust -f vllm_inference.py VllmInferenceNode2 \
  --host http://192.168.86.176:30080 \
  --users 32 --spawn-rate 1
```

### Embedding (`:30081`)

```bash
# gpu-node-1
locust -f vllm_embedding.py VllmEmbeddingNode1 \
  --host http://192.168.86.173:30081 \
  --users 16 --spawn-rate 1

# gpu-node-2
locust -f vllm_embedding.py VllmEmbeddingNode2 \
  --host http://192.168.86.176:30081 \
  --users 16 --spawn-rate 1
```

### Reranker (`:30082`)

```bash
# gpu-node-1
locust -f vllm_reranker.py VllmRerankerNode1 \
  --host http://192.168.86.173:30082 \
  --users 16 --spawn-rate 1

# gpu-node-2
locust -f vllm_reranker.py VllmRerankerNode2 \
  --host http://192.168.86.176:30082 \
  --users 16 --spawn-rate 1
```

In the Locust UI at http://localhost:8089:

- leave **Host** empty to use the user-class / CLI host, or set it to the exact backend under test
- inference: start at **4 users**, ramp to **8 / 16 / 24 / 32** at spawn rate 1

## Run (headless)

```bash
# inference — gpu-node-1, 8 users (matches max-num-seqs)
locust -f vllm_inference.py VllmInferenceNode1 \
  --host http://192.168.86.173:30080 \
  --headless --users 8 --spawn-rate 1 -t 2m

# embedding — gpu-node-2
locust -f vllm_embedding.py VllmEmbeddingNode2 \
  --host http://192.168.86.176:30081 \
  --headless --users 16 --spawn-rate 1 -t 2m

# reranker — gpu-node-2
locust -f vllm_reranker.py VllmRerankerNode2 \
  --host http://192.168.86.176:30082 \
  --headless --users 16 --spawn-rate 1 -t 2m
```

Export CSV:

```bash
locust -f vllm_inference.py VllmInferenceNode1 \
  --host http://192.168.86.173:30080 \
  --headless --users 8 --spawn-rate 1 -t 2m \
  --csv=results/vllm-infer-node1
```

## Environment overrides

```bash
export VLLM_INFER_NODE1=http://192.168.86.173:30080
export VLLM_INFER_NODE2=http://192.168.86.176:30080
export VLLM_EMBED_NODE1=http://192.168.86.173:30081
export VLLM_EMBED_NODE2=http://192.168.86.176:30081
export VLLM_RERANK_NODE1=http://192.168.86.173:30082
export VLLM_RERANK_NODE2=http://192.168.86.176:30082

export INFER_MODEL=Qwen/Qwen2.5-7B-Instruct
export EMBED_MODEL=BAAI/bge-m3
export RERANK_MODEL=BAAI/bge-reranker-v2-m3
```

## Troubleshooting

### All requests fail at ~30s with ~56-byte body

1. **Wrong Host in Locust UI** — use `--host` on the CLI or set Host to the direct node URL.
2. **Too many users for `--max-num-seqs 8`** (inference) — drop users or raise `max-num-seqs`.
3. Confirm curl smoke test passes on the same host before running Locust (see `../smoke-test/`).

### `No tasks defined on ...User`

Tasks must live on an `HttpUser` subclass (`WorkloadInferenceUser`, `WorkloadEmbeddingUser`, `WorkloadRerankerUser`), not a plain mixin.
