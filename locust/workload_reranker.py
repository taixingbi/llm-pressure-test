from locust import HttpUser, between, task

import helpers
import settings


class WorkloadRerankerUser(HttpUser):
    """Reranker workload: short docs and 512-char document pair."""

    abstract = True
    wait_time = between(0, 0.1)

    def _post_rerank(self, *, name: str, body: dict, timeout: float | None = None) -> None:
        kwargs: dict = {
            "json": body,
            "headers": helpers.trace_headers(),
            "name": name,
            "catch_response": True,
        }
        if timeout is not None:
            kwargs["timeout"] = timeout
        with self.client.post("/v1/rerank", **kwargs) as response:
            if response.status_code != 200:
                response.failure(
                    f"status={response.status_code}: {response.text[:300]}"
                )

    @task(3)
    def short_docs(self) -> None:
        body = helpers.rerank_payload(
            model=settings.RERANK_MODEL,
            query="What is Paris?",
            documents=[
                "Paris is the capital of France.",
                "Berlin is the capital of Germany.",
            ],
        )
        self._post_rerank(name="/v1/rerank [short]", body=body)

    @task(1)
    def medium_doc(self) -> None:
        doc = helpers.repeat_text(
            "Paris is the capital of France. ",
            helpers.RERANK_LONG_DOC_CHARS,
        )
        body = helpers.rerank_payload(
            model=settings.RERANK_MODEL,
            query="What is Paris?",
            documents=[doc, "Berlin is the capital of Germany."],
        )
        self._post_rerank(name="/v1/rerank [512]", body=body, timeout=60)
