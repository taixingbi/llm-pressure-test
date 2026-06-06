import time

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
                drain_start = time.perf_counter()
                try:
                    (
                        lines,
                        saw_error,
                        saw_done,
                        answer_deltas,
                        saw_answer_end,
                    ) = helpers.drain_rag_stream(response)
                except Exception as exc:
                    helpers.add_response_time_ms(
                        response, (time.perf_counter() - drain_start) * 1000
                    )
                    response.failure(exc)
                    return

                helpers.add_response_time_ms(
                    response, (time.perf_counter() - drain_start) * 1000
                )
                if saw_error:
                    response.failure("stream error event")
                elif not saw_done:
                    response.failure("stream missing done event")
                elif answer_deltas == 0 and not saw_answer_end:
                    response.failure("stream missing answer")
                elif lines == 0:
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
            name="/v1/rag/query [stream full]",
            body=body,
            stream=True,
            accept="text/event-stream",
            timeout=180,
        )
