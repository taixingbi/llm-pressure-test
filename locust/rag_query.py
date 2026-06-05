from locust import HttpUser, between, task

import helpers
import settings


class RagQueryUser(HttpUser):
    host = settings.RAG_URL
    wait_time = between(0, 0.1)

    @task
    def rag_query(self) -> None:
        request_id, session_id = helpers.unique_rag_ids()
        body = helpers.rag_payload(
            question="what is taixing visa",
            collection_base=settings.RAG_COLLECTION,
            request_id=request_id,
            session_id=session_id,
        )
        with self.client.post(
            "/v1/rag/query",
            json=body,
            headers=helpers.trace_headers(),
            name="/v1/rag/query",
            catch_response=True,
            timeout=120,
        ) as response:
            if response.status_code != 200:
                response.failure(f"status={response.status_code}")
