"""Free setup check: one short agent conversation per model provider, with the internet faked.

No API key, no Ollama and no cost. It uses the real AgentDojo code and the real Anthropic, Google and
OpenAI libraries, with only the network replaced by canned replies. For each provider it checks that a
full tool-use round trip works (the agent calls a tool, the result goes back, the final reply is read),
that tokens are counted, and that the fixes in providers.py do their job.

    python experiments/check_setup.py
"""
import importlib
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import providers  # noqa: E402

from agentdojo.agent_pipeline import AgentPipeline, InitQuery, SystemMessage, ToolsExecutionLoop, ToolsExecutor  # noqa: E402
from agentdojo.agent_pipeline.agent_pipeline import load_system_message  # noqa: E402
from agentdojo.functions_runtime import FunctionsRuntime  # noqa: E402
from agentdojo.task_suite.load_suites import get_suite  # noqa: E402

suite = get_suite("v1.2.2", "workspace")
BASE_ENV = suite.load_and_inject_default_environment({})


def http_lib(default_client_class):
    """The HTTP library a provider's client is built on (newer versions ship their own copy)."""
    for base in default_client_class.__mro__:
        root = base.__module__.split(".")[0]
        if root in ("httpx", "httpx2"):
            return importlib.import_module(root)
    return importlib.import_module("httpx")


def converse(provider, model, client):
    seen = []
    llm = providers.make_llm(provider, model, client=client(seen))
    pipeline = AgentPipeline([SystemMessage(load_system_message(None)), InitQuery(), llm,
                              ToolsExecutionLoop([ToolsExecutor(), llm], max_iters=5)])
    with providers.run_context() as usage:
        _, _, _, messages, _ = pipeline.query("Find my passwords.", FunctionsRuntime(suite.tools),
                                              BASE_ENV.model_copy(deep=True))
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "tool", "assistant"], messages
    assert messages[2]["tool_calls"][0].function == "search_files"
    assert messages[-1]["content"][0]["content"] == "Done."
    assert usage["calls"] == 2 and usage["in"] > 0, usage
    return seen


# ------------------------------------------------------------------ Anthropic
def anthropic_client(seen):
    import anthropic
    httpx = http_lib(anthropic.DefaultHttpxClient)

    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        if len(seen) == 1:
            content = [{"type": "tool_use", "id": "toolu_01", "name": "search_files", "input": {"query": "password"}}]
            stop = "tool_use"
        else:
            content, stop = [{"type": "text", "text": "Done."}], "end_turn"
        return httpx.Response(200, json={"id": "m", "type": "message", "role": "assistant", "model": body["model"],
                                         "content": content, "stop_reason": stop, "stop_sequence": None,
                                         "usage": {"input_tokens": 1000, "output_tokens": 50}})
    return anthropic.AsyncAnthropic(api_key="test", max_retries=0,
                                    http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


# ------------------------------------------------------------------ Google (Gemini)
SIGNATURE = "c2lnbmF0dXJlLTE="   # base64 of "signature-1"


def google_client(seen):
    from google import genai
    from google.genai import types
    last_error = None
    for name in ("httpx2", "httpx"):           # whichever this version of the library accepts
        try:
            httpx = importlib.import_module(name)
        except ImportError:
            continue

        def handler(request, httpx=httpx):
            body = json.loads(request.content)
            seen.append(body)
            if len(seen) == 1:
                parts = [{"functionCall": {"name": "search_files", "args": {"query": "password"}},
                          "thoughtSignature": SIGNATURE}]
            else:
                parts = [{"text": "Done."}]
            return httpx.Response(200, json={"candidates": [{"content": {"role": "model", "parts": parts},
                                                             "finishReason": "STOP"}],
                                             "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 40,
                                                               "thoughtsTokenCount": 10}})
        try:
            client = genai.Client(api_key="test", http_options=types.HttpOptions(
                httpx_client=httpx.Client(transport=httpx.MockTransport(handler))))
            client.models.generate_content(model="probe", contents="probe")   # make sure the fake network is used
            seen.clear()
            return client
        except Exception as e:  # noqa: BLE001
            seen.clear()
            last_error = e
    raise RuntimeError(f"could not attach a fake network to the Google client: {last_error}")


# ------------------------------------------------------------------ Ollama (OpenAI-compatible)
def ollama_client(seen):
    import openai
    httpx = http_lib(openai.DefaultHttpxClient)

    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        if len(seen) == 1:
            message = {"role": "assistant", "content": "", "tool_calls": [{
                "id": "call_1", "type": "function",
                "function": {"name": "search_files", "arguments": json.dumps({"query": "password"})}}]}
            finish = "tool_calls"
        else:
            message, finish = {"role": "assistant", "content": "Done."}, "stop"
        return httpx.Response(200, json={"id": "c", "object": "chat.completion", "created": 0, "model": body["model"],
                                         "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                                         "usage": {"prompt_tokens": 1000, "completion_tokens": 50, "total_tokens": 1050}})
    return openai.OpenAI(base_url=providers.OLLAMA_URL, api_key="ollama", max_retries=0,
                         http_client=httpx.Client(transport=httpx.MockTransport(handler)))


failures = 0
for provider, model, client in [("anthropic", "claude-haiku-5-5", anthropic_client),
                                 ("google", "gemini-test", google_client),
                                 ("ollama", "qwen3:8b", ollama_client)]:
    try:
        seen = converse(provider, model, client)
        if provider == "google":   # the thought signature must come back with the earlier tool call
            model_turn = [c for c in seen[1]["contents"] if c["role"] == "model"][0]
            assert model_turn["parts"][0].get("thoughtSignature") == SIGNATURE, model_turn
        if provider == "ollama":   # plain system message and plain-text content
            msgs = seen[1]["messages"]
            assert msgs[0]["role"] == "system", msgs[0]["role"]
            assert all(isinstance(m.get("content"), (str, type(None))) for m in msgs), msgs
        print(f"  {provider:10s} OK")
    except Exception as e:  # noqa: BLE001
        failures += 1
        print(f"  {provider:10s} FAILED: {type(e).__name__}: {str(e)[:300]}")

if failures:
    raise SystemExit(f"{failures} provider(s) failed; see the messages above")
print("Setup OK: AgentDojo works with the Anthropic, Google and Ollama connections.")
