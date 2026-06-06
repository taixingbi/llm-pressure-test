import settings
from workload_reranker import WorkloadRerankerUser


class GatewayRerankerUser(WorkloadRerankerUser):
    host = settings.GATEWAY_RERANK