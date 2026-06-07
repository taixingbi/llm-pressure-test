import itertools
import json
import os
import random
import time
import uuid
from dataclasses import dataclass

RAG_SSE_DEBUG = os.getenv("RAG_SSE_DEBUG", "").lower() in ("1", "true", "yes")

SMALL_PROMPT_CHARS = 300
LARGE_PROMPT_CHARS = 8000
SMALL_MAX_TOKENS = 64
MEDIUM_MAX_TOKENS = 128
STREAM_MAX_TOKENS = 256
HEAVY_MAX_TOKENS = 512
PROMPT_PROBE_CHARS = (200, 500, 1000, 1500)
RERANK_LONG_DOC_CHARS = 512

SMALL_PROMPTS = [
    "introduce new york city",
    "introduce boston",
    "introduce seattle",
    "introduce chicago",
    "introduce san francisco",
]

CITIES = [
    "New York City",
    "Boston",
    "Seattle",
    "Chicago",
    "San Francisco",
]

_id_counter = itertools.count(1)


def random_small_prompt() -> str:
    return random.choice(SMALL_PROMPTS)


def random_medium_prompt() -> str:
    city = random.choice(CITIES)
    return (
        f"Write a concise travel guide for {city} with sections for "
        "transportation, food, attractions, and safety."
    )


def random_stream_prompt() -> str:
    city = random.choice(CITIES)
    return f"Write a short {city} travel guide."


def random_long_prompt() -> str:
    city = random.choice(CITIES)
    return (
        f"Write a detailed but concise {city} travel guide. "
        "Include transportation, food, attractions, neighborhoods, "
        "budget tips, safety, and a 2-day itinerary."
    )


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


RAG_QUESTIONS = [
    "what is taixing visa",
    "What is the current US visa status of Taixing?",
]


def random_rag_question() -> str:
    return random.choice(RAG_QUESTIONS)


def rag_headers() -> dict[str, str]:
    headers = trace_headers()
    headers.update(
        {
            "X-User-Id": "taixing",
            "X-User-Roles": "hr",
            "X-User-Groups": "engineering",
            "X-User-Teams": "rag-platform",
        }
    )
    return headers


MCP_GITHUB_QUESTIONS = [
    "introduce this huntAi project",
    "what is the huntAi architecture?",
]


def random_mcp_github_question() -> str:
    return random.choice(MCP_GITHUB_QUESTIONS)


def mcp_github_payload(
    *,
    question: str,
    repo: str,
    conversation_id: str | None = None,
) -> dict:
    arguments: dict[str, str] = {"repo": repo, "question": question}
    if conversation_id:
        arguments["conversation_id"] = conversation_id

    return {
        "jsonrpc": "2.0",
        "id": next_id("mcp"),
        "method": "tools/call",
        "params": {"name": "github_search", "arguments": arguments},
    }


def rag_payload(
    *,
    question: str,
    collection_base: str,
    k: int = 5,
    k_max: int = 50,
    stream: bool = False,
) -> dict:
    return {
        "question": question,
        "collection_base": collection_base,
        "k": k,
        "k_max": k_max,
        "stream": stream,
    }


ORCHESTRATOR_RAG_QUESTION = "what is taixing visa status in us?"
ORCHESTRATOR_MCP_QUESTION = "in huntai, what gateway design?"
ORCHESTRATOR_CHAT_QUESTION = "how are you?"


def orchestrator_answer_payload(
    *,
    question: str,
    conversation_id: str | None = None,
) -> dict:
    body: dict[str, str] = {"question": question}
    if conversation_id:
        body["conversation_id"] = conversation_id
    return body


def orchestrator_stream_names(route: str) -> tuple[str, str]:
    return (
        f"/v1/orchestrator/answer [{route} stream full]",
        f"/v1/orchestrator/answer [{route} stream ttft]",
    )


CHAT_STREAM_FULL_NAME = "/v1/chat/completions [stream 256 full]"
CHAT_STREAM_TTFT_NAME = "/v1/chat/completions [stream 256 ttft]"
RAG_STREAM_FULL_NAME = "/v1/rag/query [stream full]"
RAG_STREAM_TTFT_NAME = "/v1/rag/query [stream ttft]"
MCP_STREAM_FULL_NAME = "/v1/mcp [stream full]"
MCP_STREAM_TTFT_NAME = "/v1/mcp [stream ttft]"


@dataclass
class ChatStreamDrain:
    chunks: int = 0
    content_chunks: int = 0
    saw_done: bool = False
    ttft_drain_ms: float | None = None
    drain_ms: float = 0.0
    error: Exception | None = None


def _sse_data_line_has_content(line: bytes) -> bool:
    if not line.startswith(b"data: "):
        return False

    payload = line[6:].strip()
    if not payload or payload == b"[DONE]":
        return False

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return b'"content"' in payload and b'"content":""' not in payload

    for choice in data.get("choices", []):
        delta = choice.get("delta") or {}
        if delta.get("content"):
            return True

    if data.get("text"):
        return True

    return False


def drain_chat_stream(response) -> ChatStreamDrain:
    """Drain OpenAI-style SSE until ``data: [DONE]`` (or connection error)."""
    result = ChatStreamDrain()
    drain_started = time.perf_counter()

    try:
        for line in response.iter_lines(decode_unicode=False):
            if not line:
                continue

            result.chunks += 1
            if _sse_data_line_has_content(line):
                result.content_chunks += 1
                if result.ttft_drain_ms is None:
                    result.ttft_drain_ms = (time.perf_counter() - drain_started) * 1000

            if b"[DONE]" in line:
                result.saw_done = True
                break
    except Exception as exc:
        result.error = exc
    finally:
        result.drain_ms = (time.perf_counter() - drain_started) * 1000

    return result


def drain_stream(response) -> int:
    return drain_chat_stream(response).chunks


def fire_stream_ttft(
    user,
    *,
    name: str,
    header_ms: float,
    ttft_drain_ms: float | None,
    has_token: bool,
    request_type: str = "POST",
) -> None:
    from locust.exception import CatchResponseError

    if has_token and ttft_drain_ms is not None:
        ttft_ms = header_ms + ttft_drain_ms
        exception = None
    else:
        ttft_ms = 0
        exception = CatchResponseError("missing first answer token")

    user.environment.events.request.fire(
        request_type=request_type,
        name=name,
        response_time=ttft_ms,
        response_length=0,
        exception=exception,
        context=user.context(),
    )


def finish_chat_stream(
    user,
    response,
    *,
    ttft_name: str,
) -> None:
    """Apply full-stream timing and report TTFT for chat/orchestrator SSE."""
    header_ms = response.request_meta["response_time"]
    drain = drain_chat_stream(response)
    add_response_time_ms(response, drain.drain_ms)
    fire_stream_ttft(
        user,
        name=ttft_name,
        header_ms=header_ms,
        ttft_drain_ms=drain.ttft_drain_ms,
        has_token=drain.content_chunks > 0,
    )

    if drain.error:
        response.failure(drain.error)
    elif drain.content_chunks == 0:
        response.failure("stream returned no content chunks")
    elif drain.chunks == 0:
        response.failure("stream returned no chunks")


@dataclass
class RagStreamDrain:
    lines: int = 0
    saw_error: bool = False
    saw_done: bool = False
    answer_deltas: int = 0
    saw_answer_end: bool = False
    ttft_drain_ms: float | None = None
    drain_ms: float = 0.0
    error: Exception | None = None


def _sse_data_is_done(line: bytes) -> bool:
    if not line.startswith(b"data: "):
        return False
    return b'"type": "done"' in line or b'"type":"done"' in line


def drain_orchestrator_stream(
    response,
    *,
    debug: bool = RAG_SSE_DEBUG,
    debug_max_lines: int = 20,
) -> RagStreamDrain:
    """Drain orchestrator SSE until ``data`` with ``type: done`` (or connection error)."""
    result = RagStreamDrain()
    debug_lines = 0
    drain_started = time.perf_counter()

    try:
        for line in response.iter_lines(decode_unicode=False):
            if not line:
                continue

            result.lines += 1
            if debug and debug_lines < debug_max_lines:
                print("SSE:", line[:200])
                debug_lines += 1

            if line.startswith(b"event: error"):
                result.saw_error = True
            elif line.startswith(b"event: answer_delta"):
                result.answer_deltas += 1
                if result.ttft_drain_ms is None:
                    result.ttft_drain_ms = (time.perf_counter() - drain_started) * 1000
            elif line.startswith(b"event: answer_end"):
                result.saw_answer_end = True
            elif line.startswith(b"event: done") or _sse_data_is_done(line):
                result.saw_done = True
                break
    except Exception as exc:
        result.error = exc
    finally:
        result.drain_ms = (time.perf_counter() - drain_started) * 1000

    return result


def drain_rag_stream(
    response,
    *,
    debug: bool = RAG_SSE_DEBUG,
    debug_max_lines: int = 20,
) -> RagStreamDrain:
    """Drain RAG SSE until ``event: done`` (or connection error)."""
    result = RagStreamDrain()
    debug_lines = 0
    drain_started = time.perf_counter()

    try:
        for line in response.iter_lines(decode_unicode=False):
            if not line:
                continue

            result.lines += 1
            if debug and debug_lines < debug_max_lines:
                print("SSE:", line[:200])
                debug_lines += 1

            if line.startswith(b"event: error"):
                result.saw_error = True
            elif line.startswith(b"event: answer_delta"):
                result.answer_deltas += 1
                if result.ttft_drain_ms is None:
                    result.ttft_drain_ms = (time.perf_counter() - drain_started) * 1000
            elif line.startswith(b"event: answer_end"):
                result.saw_answer_end = True
            elif line.startswith(b"event: done"):
                result.saw_done = True
                break
    except Exception as exc:
        result.error = exc
    finally:
        result.drain_ms = (time.perf_counter() - drain_started) * 1000

    return result


def add_response_time_ms(response, extra_ms: float) -> None:
    """Locust records stream response_time at headers; add body-drain duration."""
    response.request_meta["response_time"] += extra_ms

def unique_rag_ids() -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:8]
    return f"req-{suffix}", f"ses-{suffix}"
