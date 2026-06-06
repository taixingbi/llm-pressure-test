import settings
from workload_inference import WorkloadInferenceUser


class GatewayInferenceUser(WorkloadInferenceUser):
    host = settings.GATEWAY_INFER
