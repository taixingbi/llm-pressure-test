import settings
from workload_embedding import WorkloadEmbeddingUser


class VllmEmbeddingNode1(WorkloadEmbeddingUser):
    host = settings.VLLM_EMBED_NODE1


class VllmEmbeddingNode2(WorkloadEmbeddingUser):