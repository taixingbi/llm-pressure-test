from locust import HttpUser, between, task

import helpers
import settings


class _VllmEmbeddingUser(HttpUser):
    abstract = True
    wait_time = between(0, 0.1)

    @task(3)
    def small_input(self) -> None:
        text = helpers.repeat_text("hello world ", helpers.SMALL_PROMPT_CHARS)
        body = helpers.embedding_payload(model=settings.EMBED_MODEL, text=text)
        with self.client.post(
            "/v1/embeddings",
            json=body,
            headers=helpers.trace_headers(),
            name="/v1/embeddings [small]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"status={response.status_code}")

    @task(1)
    def large_input(self) -> None:
        text = helpers.repeat_text(
            "New York City is the most populous city in the United States. ",
            helpers.LARGE_PROMPT_CHARS,
        )
        body = helpers.embedding_payload(model=settings.EMBED_MODEL, text=text)
        with self.client.post(
            "/v1/embeddings",
            json=body,
            headers=helpers.trace_headers(),
            name="/v1/embeddings [large]",
            catch_response=True,
            timeout=120,
        ) as response:
            if response.status_code != 200:
                response.failure(f"status={response.status_code}")


class VllmEmbeddingNode1(_VllmEmbeddingUser):
    host = settings.VLLM_EMBED_NODE1


class VllmEmbeddingNode2(_VllmEmbeddingUser):
    host = settings.VLLM_EMBED_NODE2
