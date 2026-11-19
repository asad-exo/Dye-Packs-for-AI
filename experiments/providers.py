"""The model behind the agent: Anthropic (Claude), Google (Gemini), or a local model through Ollama.

`make_llm(provider, model)` returns the AgentDojo pipeline element for that model. Importing this
module also applies the fixes AgentDojo 0.1.35 needs for current versions of each provider's library:

  anthropic  see anthropic_compat.py
  google     keeps Gemini's "thought signatures" on tool calls. Newer Gemini models reject a
             conversation whose earlier tool calls come back without them, and AgentDojo drops them.
             Also retries with a pause when the rate limit is hit.
  ollama     talks to Ollama's OpenAI-compatible endpoint. Sends the instructions as a plain "system"
             message and message text as plain strings, which local servers expect.

Every model runs at its provider's default temperature, as it would be deployed. Token counts from
every provider go to the same counters (anthropic_compat.USAGE), and `run_context()` counts one run.
"""
from __future__ import annotations

import contextlib
import contextvars
import os

import anthropic_compat  # noqa: F401  (applies the Anthropic fixes)
from anthropic_compat import count

import agentdojo.agent_pipeline.llms.anthropic_llm as allm
import agentdojo.agent_pipeline.llms.google_llm as gllm
import agentdojo.agent_pipeline.llms.openai_llm as ollm

PROVIDERS = ("anthropic", "google", "ollama")
DEFAULT_MODEL = {"anthropic": "claude-haiku-5-5", "google": None, "ollama": "qwen3:8b"}
DEFAULT_WORKERS = {"anthropic": 8, "google": 2, "ollama": 1}   # a laptop GPU runs one model call at a time
OLLAMA_URL = "http://localhost:11434/v1"
KEY_VARS = {"anthropic": ("ANTHROPIC_API_KEY",), "google": ("GOOGLE_API_KEY", "GEMINI_API_KEY")}


def price_for(provider: str, model: str, override: tuple[float, float] | None = None) -> tuple[float, float]:
    """Dollars per million (input, output) tokens, for the cost estimate and the cost limit."""
    if override is not None:
        return override
    if provider == "ollama":
        return (0.0, 0.0)
    if provider == "anthropic":
        return anthropic_compat.PRICES.get(model, (1.0, 5.0))
    return (1.0, 5.0)   # Gemini: deliberately high unless the real price is given with --price


# ---------------------------------------------------------------------------- per-run state

_SIGNATURES: contextvars.ContextVar[dict | None] = contextvars.ContextVar("gemini_thought_signatures", default=None)


@contextlib.contextmanager
def run_context():
    """Wrap one agent run: counts its tokens and holds per-run state. Yields the token counts."""
    token = _SIGNATURES.set({})
    try:
        with anthropic_compat.track_usage() as usage:
            yield usage
    finally:
        _SIGNATURES.reset(token)


# ---------------------------------------------------------------------------- Google fixes

_google_to_message = gllm._google_to_assistant_message
_google_parts = gllm._parts_from_assistant_message
_google_request = gllm.chat_completion_request


def _google_to_message_keeping_signatures(response):
    out = _google_to_message(response)
    store = _SIGNATURES.get()
    if store is None or not out["tool_calls"]:
        return out
    call_parts = [p for p in response.candidates[0].content.parts if p.function_call]
    calls = []
    for call, part in zip(out["tool_calls"], call_parts):    # same order: one tool call per function_call part
        if part.thought_signature:
            if not call.id:
                call = call.model_copy(update={"id": f"gemini-call-{len(store)}"})
            store[call.id] = part.thought_signature
        calls.append(call)
    out["tool_calls"] = calls
    return out


def _google_parts_with_signatures(message):
    parts = _google_parts(message)
    store = _SIGNATURES.get() or {}
    calls = iter(message["tool_calls"] or [])
    for i, part in enumerate(parts):
        if part.function_call is not None:
            call = next(calls, None)
            signature = store.get(call.id) if call is not None and call.id else None
            if signature:
                parts[i] = part.model_copy(update={"thought_signature": signature})
    return parts


def _google_request_counted(model, client, contents, generation_config):
    r = _google_request(model, client, contents, generation_config=generation_config)
    u = r.usage_metadata
    if u is not None:   # thinking tokens are billed as output
        count(u.prompt_token_count or 0, (u.candidates_token_count or 0) + (u.thoughts_token_count or 0))
    return r


gllm._google_to_assistant_message = _google_to_message_keeping_signatures
gllm._parts_from_assistant_message = _google_parts_with_signatures
gllm.chat_completion_request = _google_request_counted


# ---------------------------------------------------------------------------- Ollama (OpenAI-compatible) fixes

_openai_request = ollm.chat_completion_request


def _plain_text(content):
    if isinstance(content, list) and all(isinstance(b, dict) and b.get("type") == "text" for b in content):
        return "\n".join(b.get("text", "") for b in content)
    return content


def _openai_request_local(client, model, messages, tools, reasoning_effort, temperature=0.0):
    if "api.openai.com" not in str(client.base_url):   # Ollama or another local server
        fixed = []
        for m in messages:
            m = dict(m)
            if m.get("role") == "developer":
                m["role"] = "system"
            if "content" in m:
                m["content"] = _plain_text(m["content"])
            fixed.append(m)
        messages = fixed
    r = _openai_request(client, model, messages, tools, reasoning_effort, temperature)
    if getattr(r, "usage", None) is not None:
        count(r.usage.prompt_tokens or 0, r.usage.completion_tokens or 0)
    return r


ollm.chat_completion_request = _openai_request_local


# ---------------------------------------------------------------------------- building the model

def _key(provider: str) -> str:
    for var in KEY_VARS[provider]:
        if os.environ.get(var):
            return os.environ[var]
    raise SystemExit(f"Set the {KEY_VARS[provider][-1]} environment variable first (see README.md).")


def make_llm(provider: str, model: str, client=None, base_url: str | None = None):
    """The AgentDojo pipeline element for this model. `client` replaces the real client (for tests)."""
    if provider == "anthropic":
        import anthropic
        client = client or anthropic.AsyncAnthropic(api_key=_key("anthropic"), max_retries=6)
        return allm.AnthropicLLM(client, model)
    if provider == "google":
        from google import genai
        from google.genai import types
        if client is None:
            retry = types.HttpRetryOptions(attempts=6, initial_delay=5, max_delay=60,
                                           http_status_codes=[429, 500, 502, 503, 504])
            client = genai.Client(api_key=_key("google"), http_options=types.HttpOptions(retry_options=retry))
        return gllm.GoogleLLM(model, client, temperature=None)
    if provider == "ollama":
        import openai
        client = client or openai.OpenAI(base_url=base_url or OLLAMA_URL, api_key="ollama", max_retries=2, timeout=900)
        return ollm.OpenAILLM(client, model, temperature=None)
    raise ValueError(f"unknown provider {provider!r}; choose from {PROVIDERS}")


def check_ready(provider: str, model: str, base_url: str | None = None) -> None:
    """Stop with a clear message if the key is missing, or Ollama is not running or lacks the model."""
    if provider in KEY_VARS:
        _key(provider)
        return
    import openai
    url = base_url or OLLAMA_URL
    try:
        names = [m.id for m in openai.OpenAI(base_url=url, api_key="ollama", max_retries=0, timeout=10).models.list()]
    except Exception:
        raise SystemExit(f"Ollama is not reachable at {url}. Open the Ollama app and try again.")
    if model not in names and f"{model}:latest" not in names:
        raise SystemExit(f"Ollama does not have {model}. Run:  ollama pull {model}\n"
                         f"Models it has: {', '.join(names) or 'none'}")


INFRA_MODULES = ("anthropic", "openai", "google", "httpx", "httpx2", "httpcore", "tenacity", "requests", "urllib3")


def is_infra_error(e: BaseException) -> bool:
    """True when the model could not be reached (network, rate limit, server error, missing quota),
    as opposed to the model producing output the agent could not use."""
    return type(e).__module__.split(".")[0] in INFRA_MODULES or isinstance(e, (ConnectionError, TimeoutError))
