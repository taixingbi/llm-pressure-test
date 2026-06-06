import itertools
import os
import random
import uuid

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


def orchestrator_payload(*, question: str, request_id: str, session_id: str) -> dict:
    return {
        "question": question,
        "request_id": request_id,
        "session_id": session_id,
    }


def drain_stream(response) -> int:
    chunks = 0

    for line in response.iter_lines():
        if not line:
            continue

        chunks += 1

        if b"[DONE]" in line:
            break

    return chunks


def drain_rag_stream(
    response,
    *,
    debug: bool = RAG_SSE_DEBUG,
    debug_max_lines: int = 20,
) -> tuple[int, bool, bool, int, bool]:
    """Drain RAG SSE until ``event: done``.

    Returns (lines, saw_error, saw_done, answer_deltas, saw_answer_end).
    """
    lines = 0
    debug_lines = 0
    saw_error = False
    saw_done = False
    answer_deltas = 0
    saw_answer_end = False

    for line in response.iter_lines(decode_unicode=False):
        if not line:
            continue

        lines += 1
        if debug and debug_lines < debug_max_lines:
            print("SSE:", line[:200])
            debug_lines += 1

        if line.startswith(b"event: error"):
            saw_error = True
        elif line.startswith(b"event: answer_delta"):
            answer_deltas += 1
        elif line.startswith(b"event: answer_end"):
            saw_answer_end = True
        elif line.startswith(b"event: done"):
            saw_done = True
            break

    return lines, saw_error, saw_done, answer_deltas, saw_answer_end


def add_response_time_ms(response, extra_ms: float) -> None:
    """Locust records stream response_time at headers; add body-drain duration."""
    response.request_meta["response_time"] += extra_ms

def unique_rag_ids() -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:8]
    return f"req-{suffix}", f"ses-{suffix}"
