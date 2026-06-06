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

Inference shares `inference_workload.py` (`InferenceWorkloadUser`).

## Inference workload

Tuned for current vLLM chat config:

```
--max-model-len 2048
--max-num-seqs 1
```

Task mix (`inference_workload.py`):

| Task | max_tokens | Weight | Timeout |
|------|------------|--------|---------|
| small | 64 | 6 | 60s |
| medium | 128 | 2 | 90s |
| stream | 256 | 1 | 120s |

Do **not** load-test with many `max_tokens=512` requests at this setting. Re-introduce heavier generation after `--max-num-seqs 4` or higher.

`wait_time` is `1–2s` between tasks to avoid piling requests onto a single sequence slot.

## Embedding workload

| Task | Input | Weight |
|------|-------|--------|
| small | 300 chars | 3 |
| large | 8000 chars | 1 |

## Reranker workload

| Task | Payload | Weight |
|------|---------|--------|
| short | 2 short documents | 3 |
| 512 | 512-char doc + 1 short doc | 1 |

512 chars keeps query + documents within reranker `max-model-len 2048`. A ~6000-char doc returns fast 400s.

## Run (web UI)

Pick one node and pass `--host` explicitly so the web UI does not send traffic to the wrong target. Default: **16 users**, spawn rate **1**.

### Inference (`:30080`)

```bash
# gpu-node-1
locust -f vllm_inference.py VllmInferenceNode1 \
  --host http://192.168.86.173:30080 \
  --users 16 --spawn-rate 1

# gpu-node-2
locust -f vllm_inference.py VllmInferenceNode2 \
  --host http://192.168.86.176:30080 \
  --users 16 --spawn-rate 1
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
- default run uses **16 users** at spawn rate 1

## Run (headless)

```bash
# inference — gpu-node-2
locust -f vllm_inference.py VllmInferenceNode2 \
  --host http://192.168.86.176:30080 \
  --headless --users 16 --spawn-rate 1 -t 2m

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
locust -f vllm_inference.py VllmInferenceNode2 \
  --host http://192.168.86.176:30080 \
  --headless --users 16 --spawn-rate 1 -t 2m \
  --csv=results/vllm-infer-node2
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
2. **Too many users for `--max-num-seqs 1`** (inference) — drop users or raise `max-num-seqs`.
3. Confirm curl smoke test passes on the same host before running Locust (see `../smoke-test/`).

### `No tasks defined on ...User`

Tasks must live on an `HttpUser` subclass. Inference uses `InferenceWorkloadUser`; embedding/reranker use abstract `_Vllm*User` bases.
