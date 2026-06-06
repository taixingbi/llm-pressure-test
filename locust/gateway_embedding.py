import settings
from workload_embedding import WorkloadEmbeddingUser


class GatewayEmbeddingUser(WorkloadEmbeddingUser):
    host = settings.GATEWAY_EMBED