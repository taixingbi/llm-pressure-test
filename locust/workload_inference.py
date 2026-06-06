from locust import HttpUser, between, task

import helpers
import settings


class WorkloadInferenceUser(HttpUser):
    """Light chat workload for max-model-len 2048 / max-num-seqs 8.

    Start with --users 4, then 8, 16, 24.
    With max-num-seqs 8, users above 8 test queueing behavior.
    """

    abstract = True
    connection_timeout = 10.0
    network_timeout = 200.0
    wait_time = between(1.0, 2.0)

    def _post_chat(
        self,
        *,
        name: str,
        body: dict,
        timeout: float,
        stream: bool = False,
        ttft_name: str | None = None,
    ) -> None:
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
                    helpers.finish_chat_stream(
                        self,
                        response,
                        ttft_name=ttft_name or helpers.CHAT_STREAM_TTFT_NAME,
                    )
        except Exception as exc:
            self.environment.events.request.fire(
                request_type="POST",
                name=name,
                response_time=0,
                response_length=0,
                exception=exc,
                context=self.context(),
            )

    @task(6)
    def small_chat(self) -> None:
        body = helpers.chat_payload(
            model=settings.INFER_MODEL,
            content=helpers.random_small_prompt(),
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
            content=helpers.random_medium_prompt(),
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
            content=helpers.random_stream_prompt(),
            max_tokens=256,
            stream=True,
        )
        self._post_chat(
            name=helpers.CHAT_STREAM_FULL_NAME,
            body=body,
            timeout=120,
            stream=True,
            ttft_name=helpers.CHAT_STREAM_TTFT_NAME,
        )

    @task(1)
    def long_chat(self) -> None:
        body = helpers.chat_payload(
            model=settings.INFER_MODEL,
            content=helpers.random_long_prompt(),
            max_tokens=512,
        )
        self._post_chat(
            name="/v1/chat/completions [long 512]",
            body=body,
            timeout=180,
        )
