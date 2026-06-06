from locust import HttpUser, between, task

import helpers
import settings


class GatewayRerankerUser(HttpUser):
    host = settings.GATEWAY_RERANK
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
                response.failure(
                    f"status={response.status_code}: {response.text[:300]}"
                )

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
        with self.client.post(
            "/v1/rerank",
            json=body,
            headers=helpers.trace_headers(),
            name="/v1/rerank [512]",
            catch_response=True,
            timeout=60,
        ) as response:
            if response.status_code != 200:
                response.failure(
                    f"status={response.status_code}: {response.text[:300]}"
                )
