from locust import HttpUser, between, task

import helpers
import settings


class InferenceWorkloadUser(HttpUser):
    """Light chat workload for max-model-len 2048 / max-num-seqs 1.

    With max-num-seqs 1, use --users 1 first. Four users queue behind one GPU
    slot and often hit the gateway ~30s upstream timeout.
    """

    abstract = True
    connection_timeout = 10.0
    network_timeout = 120.0
    wait_time = between(1.0, 2.0)

    def _post_chat(self, *, name: str, body: dict, timeout: float, stream: bool = False) -> None:
        try:
            with self.client.post(
                "/v1/chat/completions",
                json=body,
                headers=helpers.trace_headers(),
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
                    helpers.drain_stream(response)
        except Exception as exc:
            self.environment.events.request.fire(
                request_type="POST",
                name=name,
                response_time=0,
                response_length=0,
                exception=exc,
                context={},
            )

    @task(6)
    def small_chat(self) -> None:
        body = helpers.chat_payload(
            model=settings.INFER_MODEL,
            content="introduce new york city",
            max_tokens=64,
        )
        self._post_chat(
            name="/v1/chat/completions [small 64]",
            body=body,
            timeout=60,
        )

    @task(2)
    def medium_chat(self) -> None:
        body = helpers.chat_payload(
            model=settings.INFER_MODEL,
            content=(
                "Write a concise travel guide for New York City with sections for "
                "transportation, food, attractions, and safety."
            ),
            max_tokens=128,
        )
        self._post_chat(
            name="/v1/chat/completions [medium 128]",
            body=body,
            timeout=90,
        )

    @task(1)
    def stream_chat(self) -> None:
        body = helpers.chat_payload(
            model=settings.INFER_MODEL,
            content="Write a short New York City travel guide.",
            max_tokens=256,
            stream=True,
        )
        self._post_chat(
            name="/v1/chat/completions [stream 256]",
            body=body,
            timeout=120,
            stream=True,
        )
