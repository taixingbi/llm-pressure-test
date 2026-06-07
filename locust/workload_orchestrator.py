from locust import HttpUser, between, task

import helpers


class WorkloadOrchestratorUser(HttpUser):
    """Shared orchestrator answer POST + SSE drain."""

    abstract = True
    wait_time = between(1.0, 2.0)
    network_timeout = 300.0

    def _post_answer(self, *, question: str, route: str) -> None:
        headers = helpers.rag_headers()
        body = helpers.orchestrator_answer_payload(question=question)
        full_name, ttft_name = helpers.orchestrator_stream_names(route)

        with self.client.post(
            "/v1/orchestrator/answer",
            json=body,
            headers=headers,
            name=full_name,
            stream=True,
            catch_response=True,
            timeout=300,
        ) as response:
            if response.status_code != 200:
                response.failure(
                    f"status={response.status_code}: {response.text[:300]}"
                )
                return

            header_ms = response.request_meta["response_time"]
            drain = helpers.drain_orchestrator_stream(response)
            helpers.add_response_time_ms(response, drain.drain_ms)
            helpers.fire_stream_ttft(
                self,
                name=ttft_name,
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


class WorkloadOrchestratorRAGUser(WorkloadOrchestratorUser):
    @task
    def answer_rag(self) -> None:
        self._post_answer(
            question=helpers.ORCHESTRATOR_RAG_QUESTION,
            route="rag",
        )


class WorkloadOrchestratorMCPUser(WorkloadOrchestratorUser):
    @task
    def answer_mcp(self) -> None:
        self._post_answer(
            question=helpers.ORCHESTRATOR_MCP_QUESTION,
            route="mcp",
        )


class WorkloadOrchestratorChatUser(WorkloadOrchestratorUser):
    @task
    def answer_chat(self) -> None:
        self._post_answer(
            question=helpers.ORCHESTRATOR_CHAT_QUESTION,
            route="chat",
        )
