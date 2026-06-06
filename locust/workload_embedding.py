from locust import HttpUser, between, task

import helpers
import settings


class WorkloadEmbeddingUser(HttpUser):
    """Embedding workload: small (300 chars) and large (8000 chars) inputs."""

    abstract = True
    wait_time = between(0, 0.1)

    def _post_embedding(self, *, name: str, body: dict, timeout: float | None = None) -> None:
        kwargs: dict = {
            "json": body,
            "headers": helpers.trace_headers(),
            "name": name,
            "catch_response": True,
        }
        if timeout is not None:
            kwargs["timeout"] = timeout

        with self.client.post("/v1/embeddings", **kwargs) as response:
            if response.status_code != 200:
                response.failure(f"status={response.status_code}")
                return

            try:
                data = response.json()
            except ValueError:
                response.failure("invalid json")
                return

            if "data" not in data or not data["data"]:
                response.failure("missing embedding data")

    @task(3)
    def small_input(self) -> None:
        text = helpers.repeat_text("hello world ", helpers.SMALL_PROMPT_CHARS)
        body = helpers.embedding_payload(model=settings.EMBED_MODEL, text=text)
        self._post_embedding(
            name="/v1/embeddings [small 300]",
            body=body,
            timeout=30,
        )

    @task(1)
    def large_input(self) -> None:
        text = helpers.repeat_text(
            "New York City is the most populous city in the United States. ",
            helpers.LARGE_PROMPT_CHARS,
        )
        body = helpers.embedding_payload(model=settings.EMBED_MODEL, text=text)
        self._post_embedding(
            name="/v1/embeddings [large 8000]",
            body=body,
            timeout=120,
        )
