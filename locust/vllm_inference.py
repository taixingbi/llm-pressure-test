import settings
from workload_inference import WorkloadInferenceUser


class VllmInferenceNode1(WorkloadInferenceUser):
    host = settings.VLLM_INFER_NODE1


class VllmInferenceNode2(WorkloadInferenceUser):
    host = settings.VLLM_INFER_NODE2
