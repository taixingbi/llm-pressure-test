import settings
from workload_rag import WorkloadRagUser


class RagQueryUser(WorkloadRagUser):
    host = settings.RAG_URL
