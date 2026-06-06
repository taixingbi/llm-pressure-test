import settings
from workload_mcp import WorkloadMcpUser


class McpGithubUser(WorkloadMcpUser):
    host = settings.MCP_URL
