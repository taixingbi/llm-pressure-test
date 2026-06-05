import settings
from inference_workload import InferenceWorkloadUser


class GatewayInferenceUser(InferenceWorkloadUser):
    host = settings.GATEWAY_INFER
