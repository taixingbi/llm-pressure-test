from locust import HttpUser, between, task

import helpers
import settings


class OrchestratorUser(HttpUser):
    host = settings.ORCH_URL
    wait_time = between(0, 0.1)

    @task
    def stream_answer(self) -> None:
        request_id = helpers.next_id("req")
        session_id = helpers.next_id("ses")
        body = helpers.orchestrator_payload(
            question="what is taixing visa status?",
            request_id=request_id,
            session_id=session_id,
        )
        with self.client.post(
            "/orchestrator/stream-answer",
            json=body,
            headers=helpers.trace_headers(),
            name="/orchestrator/stream-answer",
            stream=True,
            catch_response=True,
            timeout=300,
        ) as response:
            if response.status_code != 200:
                response.failure(f"status={response.status_code}")
            else:
                helpers.drain_stream(response)
