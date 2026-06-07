# MCP GitHub search (Locust)

Load test for `POST /v1/mcp` (`tools/call` → `github_search`). See [README.md](README.md) for setup and shared configuration.

Smoke test (run before Locust): `../smoke-test/mcp-github.md`.

## Locust files

| Service | File | User class | Port |
|---------|------|------------|------|
| MCP GitHub | `mcp_github.py` | `McpGithubUser` | 30191 |

Shared workload: `workload_mcp.py` (`WorkloadMcpUser`).

## Architecture

Each request is JSON-RPC over SSE — no non-streaming mode:

| Phase | Typical ms | Notes |
|-------|------------|-------|
| `retrieve_rerank` | ~1.3s | GitHub fetch + rerank |
| `chat` | ~7–8s | LLM answer generation |
| `total` | ~8–10s | from `event: done` → `latency_ms.total` |

Confirm smoke test in `../smoke-test/mcp-github.md` before load testing.

## MCP workload

Task mix (`workload_mcp.py`):

| Task | Mode | Weight | Locust name | Timeout |
|------|------|--------|-------------|---------|
| `mcp_github_search` | SSE only | 1 | `/v1/mcp [stream full]` + `[stream ttft]` | 180s |

- Questions rotate via `helpers.random_mcp_github_question()` (`helpers.MCP_GITHUB_QUESTIONS`)
- Repo from `MCP_GITHUB_REPO` (default: `layer-web-v1` blog path)
- Correlation ids in **headers** (`X-Request-Id`, `X-Session-Id`, `X-Trace-Id`)
- One stream request reports **two** Locust stats: `[stream ttft]` (first `answer_delta`) and `[stream full]` (through `event: done`)
- Stream fails on `event: error`, missing `event: done`, missing answer tokens, or truncated body
- Locust `stream=True` header timing is corrected for full drain
- Debug first SSE lines: `RAG_SSE_DEBUG=1 locust -f mcp_github.py ...` (reuses `drain_rag_stream`)

SSE sequence: `event: meta` → `event: answer_delta` (`data.text`) → `event: done` (full `answer`, `citations`, `latency_ms`).

`wait_time` is `1–2s` between tasks.

### Test matrix

MCP GitHub is slow (~9s per request). Start at 1 user.

| Users | Meaning |
|-------|---------|
| 1 | Baseline |
| 2 | Light load |
| 4 | Moderate |

**Pass condition:** `fail = 0`, p95 &lt; 60s, p99 &lt; 120s.

## Run (web UI)

```bash
locust -f mcp_github.py \
  --host http://192.168.86.179:30191 \
  --users 1 --spawn-rate 1
```

Ramp after each level is stable:

```bash
locust -f mcp_github.py \
  --host http://192.168.86.179:30191 \
  --users 2 --spawn-rate 1
```

In the Locust UI at http://localhost:8089:

- leave **Host** empty to use the CLI `--host`
- start at **1 user**, spawn rate **1**

## Run (headless)

```bash
locust -f mcp_github.py \
  --host http://192.168.86.179:30191 \
  --headless --users 2 --spawn-rate 1 -t 2m
```

Export CSV:

```bash
locust -f mcp_github.py \
  --host http://192.168.86.179:30191 \
  --headless --users 2 --spawn-rate 1 -t 2m \
  --csv=results/mcp-github
```

## Environment overrides

```bash
export MCP_URL=http://192.168.86.179:30191
export MCP_GITHUB_REPO="https://github.com/taixingbi/layer-web-v1/tree/main/app/blog"
```

## Troubleshooting

### HTTP non-200

Re-run smoke test from `../smoke-test/mcp-github.md`. Check MCP pod logs and GitHub API reachability.

### `stream missing done event` / `missing answer`

Usually truncated SSE or tool error mid-stream. Check Locust **Failures** tab and re-run smoke test with `--max-time 120`.

### High latency / timeouts

- Drop `--users` (try 1)
- MCP includes GitHub fetch + LLM — expect ~8–10s per request at low load
- Increase timeout only if p99 legitimately exceeds 180s under load
