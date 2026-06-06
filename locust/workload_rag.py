from locust import HttpUser, between, task

import helpers
import settings


class WorkloadRagUser(HttpUser):
    """RAG query workload: JSON and SSE, aligned with smoke-test/rag-query.md."""

    abstract = True
    wait_time = between(0.5, 1.0)
    network_timeout = 180.0

    def _post_rag(
        self,
        *,
        name: str,
        body: dict,
        stream: bool,
        accept: str,
        timeout: float,
    ) -> None:
        headers = helpers.rag_headers()
        headers["Accept"] = accept

        with self.client.post(
            "/v1/rag/query",
            json=body,
            headers=headers,
            name=name,
            stream=stream,
            catch_response=True,
            timeout=timeout,
        ) as response:
            if response.status_code != 200:
                response.failure(
                    f"status={response.status_code}: {response.text[:300]}"
                )
                return

            if stream:
                header_ms = response.request_meta["response_time"]
                drain = helpers.drain_rag_stream(response)
                helpers.add_response_time_ms(response, drain.drain_ms)
                helpers.fire_stream_ttft(
                    self,
                    name=helpers.RAG_STREAM_TTFT_NAME,
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
                elif drain.answer_deltas == 0 and not drain.saw_answer_end:
                    response.failure("stream missing answer")
                elif drain.lines == 0:
                    response.failure("stream returned no events")
                return

            try:
                data = response.json()
            except ValueError:
                response.failure("invalid json")
                return

            answer = data.get("answer")
            if not answer:
                response.failure("missing answer")

    @task(1)
    def rag_query_json(self) -> None:
        body = helpers.rag_payload(
            question=helpers.random_rag_question(),
            collection_base=settings.RAG_COLLECTION,
            stream=False,
        )
        self._post_rag(
            name="/v1/rag/query [json]",
            body=body,
            stream=False,
            accept="application/json",
            timeout=180,
        )

    @task(1)
    def rag_query_stream(self) -> None:
        body = helpers.rag_payload(
            question=helpers.random_rag_question(),
            collection_base=settings.RAG_COLLECTION,
            stream=True,
        )
        self._post_rag(
            name=helpers.RAG_STREAM_FULL_NAME,
            body=body,
            stream=True,
            accept="text/event-stream",
            timeout=180,
        )
