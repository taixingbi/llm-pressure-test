import settings
from workload_reranker import WorkloadRerankerUser


class VllmRerankerNode1(WorkloadRerankerUser):
    host = settings.VLLM_RERANK_NODE1


class VllmRerankerNode2(WorkloadRerankerUser):