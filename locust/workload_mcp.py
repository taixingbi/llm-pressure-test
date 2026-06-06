from locust import HttpUser, between, task

import helpers
import settings


class WorkloadMcpUser(HttpUser):
    """MCP GitHub search workload — JSON-RPC SSE only."""

    abstract = True
    wait_time = between(1.0, 2.0)
    network_timeout = 180.0

    def _post_mcp_github(self) -> None:
        headers = helpers.trace_headers()
        headers["Accept"] = "text/event-stream"
        body = helpers.mcp_github_payload(
            question=helpers.random_mcp_github_question(),
            repo=settings.MCP_GITHUB_REPO,
        )

        with self.client.post(
            "/v1/mcp",
            json=body,
            headers=headers,
            name=helpers.MCP_STREAM_FULL_NAME,
            stream=True,
            catch_response=True,
            timeout=180,
        ) as response:
            if response.status_code != 200:
                response.failure(
                    f"status={response.status_code}: {response.text[:300]}"
                )
                return

            header_ms = response.request_meta["response_time"]
            drain = helpers.drain_rag_stream(response)
            helpers.add_response_time_ms(response, drain.drain_ms)
            helpers.fire_stream_ttft(
                self,
                name=helpers.MCP_STREAM_TTFT_NAME,
                header_ms=header_ms,
                ttft_drain_ms=drain.ttft_drain_ms,
                has_token=drain.answer_deltas > 0,
            )

            if drain.error:
                response.failure(drain.error)
            elif drain.saw_error:
                response.failure("stream error event")
            elif not drain.saw_done:
                response.failure("stream missing done event")
            elif drain.answer_deltas == 0:
                response.failure("stream missing answer")

    @task
    def mcp_github_search(self) -> None:
        self._post_mcp_github()
