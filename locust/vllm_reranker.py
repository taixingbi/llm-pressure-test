from locust import HttpUser, between, task

import helpers
import settings


class _VllmRerankerUser(HttpUser):
    abstract = True
    wait_time = between(0, 0.1)

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
        with self.client.post(
            "/v1/rerank",
            json=body,
            headers=helpers.trace_headers(),
            name="/v1/rerank [short]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"status={response.status_code}")

    @task(1)
    def long_doc(self) -> None:
        long_doc = helpers.repeat_text("Paris is the capital of France. ", 6000)
        body = helpers.rerank_payload(
            model=settings.RERANK_MODEL,
            query="What is Paris?",
            documents=[long_doc, "Berlin is the capital of Germany."],
        )
        with self.client.post(
            "/v1/rerank",
            json=body,
            headers=helpers.trace_headers(),
            name="/v1/rerank [long]",
            catch_response=True,
            timeout=120,
        ) as response:
            if response.status_code != 200:
                response.failure(f"status={response.status_code}")


class VllmRerankerNode1(_VllmRerankerUser):
    host = settings.VLLM_RERANK_NODE1


class VllmRerankerNode2(_VllmRerankerUser):
    host = settings.VLLM_RERANK_NODE2
