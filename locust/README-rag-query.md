# RAG query (Locust)

Load test for `POST /v1/rag/query`. See [README.md](README.md) for setup and shared configuration.

Parent curl benchmark: `../rag-query.md`.

Smoke test (run before Locust): `../smoke-test/rag-query.md`.

## Locust files

| Service | File | User class | Port |
|---------|------|------------|------|
| RAG query | `rag_query.py` | `RagQueryUser` | 30183 |

Shared workload: `workload_rag.py` (`WorkloadRagUser`).

## Architecture

Each RAG request hits the full chain:

| Upstream | Default | Notes |
|----------|---------|-------|
| Qdrant | `http://qdrant:6333` (in-cluster) | not host `:6333` |
| Embedding gateway | `30181` | |
| Reranker gateway | `30182` | |
| Inference gateway | `30180` | |

Confirm smoke test and prerequisites in `../smoke-test/rag-query.md` before load testing.

## RAG workload

Task mix (`workload_rag.py`):

| Task | Mode | Weight | Locust name | Timeout |
|------|------|--------|-------------|---------|
| `rag_query_json` | JSON (`stream: false`) | 1 | `/v1/rag/query [json]` | 180s |
| `rag_query_stream` | SSE (`stream: true`) | 1 | `/v1/rag/query [stream full]` + `[stream ttft]` | 180s |

- Questions rotate via `helpers.random_rag_question()` (`helpers.RAG_QUESTIONS`)
- Correlation ids in **headers only** (`X-Request-Id`, `X-Session-Id`, `X-Trace-Id`) — not in JSON body
- Access-control headers: `X-User-Id`, `X-User-Roles`, `X-User-Groups`, `X-User-Teams`
- JSON tasks fail if `answer` is missing
- One stream request reports **two** Locust stats: `[stream ttft]` (first `answer_delta`) and `[stream full]` (through `event: done`)
- Stream fails on `event: error`, missing `event: done`, missing answer tokens, or truncated body
- Locust records `stream=True` response time at **headers only**; workload adds body-drain duration so `[stream full]` ≈ JSON latency (~2.5–3.5s); `[stream ttft]` ≈ embed + retrieve + first token (~300–800ms)
- Debug first SSE lines: `RAG_SSE_DEBUG=1 locust -f rag_query.py ...`

`wait_time` is `0.5–1s` between tasks.

### Test matrix

RAG is end-to-end (Qdrant + 3 gateways + LLM). Start low and ramp slowly.

| Users | Meaning |
|-------|---------|
| 2 | Baseline |
| 4 | Light load |
| 8 | Moderate |
| 16 | Stress |

**Pass condition:** `fail = 0`, p95 &lt; 30s, p99 &lt; 60s (RAG is slower than single-gateway calls).

## Run (web UI)

Pass `--host` explicitly:

```bash
locust -f rag_query.py \
  --host http://192.168.86.179:30183 \
  --users 2 --spawn-rate 1
```

Ramp after each level is stable:

```bash
locust -f rag_query.py \
  --host http://192.168.86.179:30183 \
  --users 16 --spawn-rate 1
```

In the Locust UI at http://localhost:8089:

- leave **Host** empty to use the CLI `--host`
- start at **2 users**, spawn rate **1**

## Run (headless)

```bash
locust -f rag_query.py \
  --host http://192.168.86.179:30183 \
  --headless --users 4 --spawn-rate 1 -t 2m
```

Export CSV:

```bash
locust -f rag_query.py \
  --host http://192.168.86.179:30183 \
  --headless --users 4 --spawn-rate 1 -t 2m \
  --csv=results/rag-query
```

## Environment overrides

```bash
export RAG_URL=http://192.168.86.179:30183
export RAG_COLLECTION=taixing_knowledge
```

`ENV=dev` on the RAG service resolves `taixing_knowledge` → collection `taixing_knowledge_dev` in Qdrant.

## Troubleshooting

### `event: error` + `ConnectError`

RAG pod cannot reach an upstream. From `server-node-1`:

```bash
sudo k3s kubectl -n ai-dev exec deploy/layer-rag-query -- \
  curl -sS -o /dev/null -w "qdrant=%{http_code}\n" http://qdrant:6333/collections

curl -sS -o /dev/null -w "embed=%{http_code}\n"  http://192.168.86.179:30181/health
curl -sS -o /dev/null -w "rerank=%{http_code}\n" http://192.168.86.179:30182/health
curl -sS -o /dev/null -w "infer=%{http_code}\n"  http://192.168.86.179:30180/health
```

Fix whichever is not `200`. See `../smoke-test/rag-query.md`.

### HTTP 400

Do not put `request_id`, `session_id`, or `trace_id` in the JSON body — headers only.

### High latency / timeouts

- Drop `--users` (try 2)
- Confirm gateway smoke tests pass independently
- Check gateway inference queue (`README-gateway.md`)

### `stream missing done event` / `missing answer`

Usually partial failure mid-chain. Check Locust **Failures** tab for status codes and re-run smoke test.
