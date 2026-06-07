# Orchestrator answer (Locust)

Load test for `POST /v1/orchestrator/answer` (unified routing). See [README.md](README.md) for setup.

Smoke test (run before Locust): `../smoke-test/orchestrator.md`.

## Locust files

| Service | File | User class | Port |
|---------|------|------------|------|
| Orchestrator RAG | `orchestrator.py` | `OrchestratorRAGUser` | 30184 |
| Orchestrator MCP | `orchestrator.py` | `OrchestratorMCPUser` | 30184 |
| Orchestrator chat | `orchestrator.py` | `OrchestratorChatUser` | 30184 |

Shared workload: `workload_orchestrator.py` — one user class per route so stats are not mixed.

## Routes

| User class | Route | Question | Locust names |
|------------|-------|----------|--------------|
| `OrchestratorRAGUser` | RAG | visa status | `[rag stream full]` + `[rag stream ttft]` |
| `OrchestratorMCPUser` | MCP GitHub | gateway design | `[mcp stream full]` + `[mcp stream ttft]` |
| `OrchestratorChatUser` | chitchat | how are you? | `[chat stream full]` + `[chat stream ttft]` |

Run **one user class at a time** to isolate route latency (especially MCP debugging).

- Correlation ids in **headers only** (`X-Request-Id`, `X-Session-Id`, `X-Trace-Id`)
- Access-control headers match smoke test (`X-User-*` via `helpers.rag_headers()`)
- Each request reports TTFT + full stream stats; body-drain timing corrected
- SSE drain: `event: answer_delta` → `data: {"type": "done", ...}` (orchestrator uses data-line done, not `event: done`)

`wait_time` is `1–2s` between tasks.

### Test matrix

| Users | Meaning |
|-------|---------|
| 2 | Baseline |
| 4 | Light load |
| 8 | Moderate |

**Pass condition:** `fail = 0`, p95 &lt; 60s, p99 &lt; 120s (MCP often slowest).

## Run one route (recommended)

MCP only:

```bash
locust -f orchestrator.py OrchestratorMCPUser \
  --host http://192.168.86.179:30184 \
  --users 3 --spawn-rate 1
```

RAG only:

```bash
locust -f orchestrator.py OrchestratorRAGUser \
  --host http://192.168.86.179:30184 \
  --users 16 --spawn-rate 1
```

Chat only:

```bash
locust -f orchestrator.py OrchestratorChatUser \
  --host http://192.168.86.179:30184 \
  --users 16 --spawn-rate 1
```

In the Locust UI, pick the user class from the dropdown when not passed on the CLI.

## Run (headless)

```bash
locust -f orchestrator.py OrchestratorMCPUser \
  --host http://192.168.86.179:30184 \
  --headless --users 4 --spawn-rate 1 -t 2m
```

## Environment overrides

```bash
export ORCH_URL=http://192.168.86.179:30184
```
