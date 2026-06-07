import settings
from workload_orchestrator import (
    WorkloadOrchestratorChatUser,
    WorkloadOrchestratorMCPUser,
    WorkloadOrchestratorRAGUser,
)


class OrchestratorRAGUser(WorkloadOrchestratorRAGUser):
    host = settings.ORCH_URL


class OrchestratorMCPUser(WorkloadOrchestratorMCPUser):
    host = settings.ORCH_URL


class OrchestratorChatUser(WorkloadOrchestratorChatUser):
    host = settings.ORCH_URL
