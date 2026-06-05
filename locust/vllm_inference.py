import settings
from inference_workload import InferenceWorkloadUser


class VllmInferenceNode1(InferenceWorkloadUser):
    host = settings.VLLM_INFER_NODE1


class VllmInferenceNode2(InferenceWorkloadUser):
    host = settings.VLLM_INFER_NODE2
