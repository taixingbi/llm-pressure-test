import os

VLLM_INFER_NODE1 = os.getenv("VLLM_INFER_NODE1", "http://192.168.86.173:30080")
VLLM_INFER_NODE2 = os.getenv("VLLM_INFER_NODE2", "http://192.168.86.176:30080")
VLLM_EMBED_NODE1 = os.getenv("VLLM_EMBED_NODE1", "http://192.168.86.173:30081")
VLLM_EMBED_NODE2 = os.getenv("VLLM_EMBED_NODE2", "http://192.168.86.176:30081")
VLLM_RERANK_NODE1 = os.getenv("VLLM_RERANK_NODE1", "http://192.168.86.173:30082")
VLLM_RERANK_NODE2 = os.getenv("VLLM_RERANK_NODE2", "http://192.168.86.176:30082")

GATEWAY_INFER = os.getenv("GATEWAY_INFER", "http://192.168.86.179:30180")
GATEWAY_EMBED = os.getenv("GATEWAY_EMBED", "http://192.168.86.179:30181")
GATEWAY_RERANK = os.getenv("GATEWAY_RERANK", "http://192.168.86.179:30182")

RAG_URL = os.getenv("RAG_URL", "http://192.168.86.179:30183")
MCP_URL = os.getenv("MCP_URL", "http://192.168.86.179:30191")
ORCH_URL = os.getenv("ORCH_URL", "http://192.168.86.179:30184")

INFER_MODEL = os.getenv("INFER_MODEL", "Qwen/Qwen2.5-7B-Instruct")
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-m3")
RERANK_MODEL = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
RAG_COLLECTION = os.getenv("RAG_COLLECTION", "taixing_knowledge")
MCP_GITHUB_REPO = os.getenv(
    "MCP_GITHUB_REPO",
    "https://github.com/taixingbi/layer-web-v1/tree/main/app/blog",
)
