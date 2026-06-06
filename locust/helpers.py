import itertools
import uuid

SMALL_PROMPT_CHARS = 300
LARGE_PROMPT_CHARS = 8000
SMALL_MAX_TOKENS = 64
MEDIUM_MAX_TOKENS = 128
STREAM_MAX_TOKENS = 256
# Reserve 512-token workloads until max-num-seqs >= 4 and max-model-len is raised.
HEAVY_MAX_TOKENS = 512
PROMPT_PROBE_CHARS = (200, 500, 1000, 1500)
RERANK_LONG_DOC_CHARS = 512

_id_counter = itertools.count(1)


def next_id(prefix: str) -> str:
    return f"{prefix}-{next(_id_counter)}"


def trace_headers() -> dict[str, str]:
    rid = next_id("req")
    return {
        "X-Request-Id": rid,
        "X-Trace-Id": next_id("trace"),
        "X-Session-Id": next_id("ses"),
    }


def repeat_text(chunk: str, chars: int) -> str:
    if chars <= 0:
        return ""
    repeats = (chars // len(chunk)) + 1
    return (chunk * repeats)[:chars]


def chat_payload(
    *,
    model: str,
    content: str,
    max_tokens: int,
    stream: bool = False,
) -> dict:
    body: dict = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    if stream:
        body["stream"] = True
    return body


def embedding_payload(*, model: str, text: str) -> dict:
    return {"model": model, "input": text}


def rerank_payload(
    *,
    model: str,
    query: str,
    documents: list[str],
    top_n: int = 2,
) -> dict:
    return {
        "model": model,
        "query": query,
        "documents": documents,
        "top_n": top_n,
    }


def rag_payload(
    *,
    question: str,
    collection_base: str,
    request_id: str,
    session_id: str,
    k: int = 5,
    k_max: int = 40,
) -> dict:
    return {
        "question": question,
        "collection_base": collection_base,
        "request_id": request_id,
        "session_id": session_id,
        "k": k,
        "k_max": k_max,
    }


def orchestrator_payload(*, question: str, request_id: str, session_id: str) -> dict:
    return {
        "question": question,
        "request_id": request_id,
        "session_id": session_id,
    }


def drain_stream(response) -> None:
    for _ in response.iter_content(chunk_size=4096):
        pass


def unique_rag_ids() -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:8]
    return f"req-{suffix}", f"ses-{suffix}"
