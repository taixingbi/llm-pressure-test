# Gateway (Locust)

Load tests for gateway inference, embedding, and reranker. See [README.md](README.md) for setup and shared configuration.

Parent curl benchmarks: `gateway-inference.md`, `gateway-embedding.md`, `gateway-reranker.md`.

Smoke tests (run before Locust): `../smoke-test/gateway-inference.md`, `gateway-embedding.md`, `gateway-reranker.md`.

## Locust files

| Service | File | User class | Port |
|---------|------|------------|------|
| Inference | `gateway_inference.py` | `GatewayInferenceUser` | 30180 |
| Embedding | `gateway_embedding.py` | `GatewayEmbeddingUser` | 30181 |
| Reranker | `gateway_reranker.py` | `GatewayRerankerUser` | 30182 |

Inference shares `inference_workload.py` (`InferenceWorkloadUser`).

## Inference workload

Tuned for current vLLM chat config behind the gateway:

```
--max-model-len 2048
--max-num-seqs 1
```

Gateway concurrency (`layer-gateway-inference` ConfigMap):

| Limit | Value | Config key |
|-------|-------|------------|
| Per backend max in-flight | 16 | `backends[].hard_limit` |
| Global max in-flight | 32 | 2 backends × 16 (no separate global key) |

Per-backend `soft_limit` is 12 (overload penalty above 12; hard cap at 16).

Task mix (`inference_workload.py`):

| Task | max_tokens | Weight | Timeout |
|------|------------|--------|---------|
| small | 64 | 6 | 60s |
| medium | 128 | 2 | 90s |
| stream | 256 | 1 | 120s |

Start with **1 user** on the gateway. Ramp to **16** (one backend saturated), then **32** (global cap). Drop back if failures or ~30s latency.

`wait_time` is `1–2s` between tasks.

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

## Run (web UI)

Pass `--host` explicitly so the web UI does not send traffic to the wrong target.

### Inference (`:30180`)

```bash
locust -f gateway_inference.py \
  --host http://192.168.86.179:30180 \
  --users 1 --spawn-rate 1
```

Ramp after stable 1-user run (gateway hard_limit 16/backend, 32 global):

```bash
locust -f gateway_inference.py \
  --host http://192.168.86.179:30180 \
  --users 8 --spawn-rate 1

locust -f gateway_inference.py \
  --host http://192.168.86.179:30180 \
  --users 16 --spawn-rate 1

locust -f gateway_inference.py \
  --host http://192.168.86.179:30180 \
  --users 32 --spawn-rate 1
```

### Embedding (`:30181`)

```bash
locust -f gateway_embedding.py \
  --host http://192.168.86.179:30181 \
  --users 16 --spawn-rate 1
```

### Reranker (`:30182`)

```bash
locust -f gateway_reranker.py \
  --host http://192.168.86.179:30182 \
  --users 16 --spawn-rate 1
```

In the Locust UI at http://localhost:8089:

- leave **Host** empty to use the user-class / CLI host
- inference: start at **1 user**; embedding/reranker: **16 users** at spawn rate 1

## Run (headless)

```bash
# inference
locust -f gateway_inference.py \
  --host http://192.168.86.179:30180 \
  --headless --users 1 --spawn-rate 1 -t 2m

# embedding
locust -f gateway_embedding.py \
  --host http://192.168.86.179:30181 \
  --headless --users 16 --spawn-rate 1 -t 2m

# reranker
locust -f gateway_reranker.py \
  --host http://192.168.86.179:30182 \
  --headless --users 16 --spawn-rate 1 -t 2m
```

Export CSV:

```bash
locust -f gateway_inference.py \
  --host http://192.168.86.179:30180 \
  --headless --users 1 --spawn-rate 1 -t 2m \
  --csv=results/gateway-infer

locust -f gateway_reranker.py --headless --users 16 --spawn-rate 1 -t 2m \
  --csv=results/gateway-rerank
```

## Environment overrides

```bash
export GATEWAY_INFER=http://192.168.86.179:30180
export GATEWAY_EMBED=http://192.168.86.179:30181
export GATEWAY_RERANK=http://192.168.86.179:30182

export INFER_MODEL=Qwen/Qwen2.5-7B-Instruct
export EMBED_MODEL=BAAI/bge-m3
export RERANK_MODEL=BAAI/bge-reranker-v2-m3
```

## Troubleshooting

### All requests fail at ~30s with ~56-byte body

Typical with gateway inference when too many users queue behind `--max-num-seqs 1` on the backend.

1. Drop to `--users 1` for inference.
2. Check **Failures** tab for `status=502/504: ...`.
3. Confirm smoke test passes: `../smoke-test/gateway-inference.md`.
4. Compare with direct node: [README-direct-vllm.md](README-direct-vllm.md). Fast direct + slow gateway = gateway queue/timeout.

### Reranker `[512]` failures

512-char documents are the max tested payload. Larger docs return fast 400s.

### `No tasks defined on GatewayInferenceUser`

Tasks must live on an `HttpUser` subclass (`InferenceWorkloadUser`), not a plain mixin.
