"""Free setup check: runs an AI agent in AgentDojo with the internet connection faked.

No API key needed and nothing is spent. It uses the real AgentDojo and Anthropic code, with only the
network replaced by canned replies, and checks that a full tool-use round trip works: the request is
built correctly, the agent calls a tool, the tool result goes back, and the reply is read.

    python experiments/check_setup.py
"""
import json
import os
import sys

import anthropic
try:                                   # Anthropic library 2.x ships its own copy of httpx
    import httpx2 as httpx
except ImportError:                    # older versions use httpx itself
    import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anthropic_compat  # noqa: E402
import agentdojo.agent_pipeline.llms.anthropic_llm as allm
from agentdojo.agent_pipeline import AgentPipeline, InitQuery, SystemMessage, ToolsExecutionLoop, ToolsExecutor
from agentdojo.agent_pipeline.agent_pipeline import load_system_message
from agentdojo.functions_runtime import FunctionsRuntime
from agentdojo.task_suite.load_suites import get_suite

SEEN = []
def handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    SEEN.append(body)
    assert "temperature" not in body and body["max_tokens"] <= 4096
    n = len(SEEN)
    if n == 1:
        content = [{"type": "text", "text": "Let me look."},
                   {"type": "tool_use", "id": "toolu_01", "name": "search_files", "input": {"query": "password"}}]
        stop = "tool_use"
    else:
        content = [{"type": "text", "text": "Done."}]
        stop = "end_turn"
    return httpx.Response(200, json={"id": f"msg_{n}", "type": "message", "role": "assistant", "model": body["model"],
                                     "content": content, "stop_reason": stop, "stop_sequence": None,
                                     "usage": {"input_tokens": 1000, "output_tokens": 50}})

client = anthropic.AsyncAnthropic(api_key="test-not-a-key", max_retries=0,
                                  http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
suite = get_suite("v1.2.2", "workspace")
env = suite.load_and_inject_default_environment({})
llm = allm.AnthropicLLM(client, "claude-haiku-5-5")
p = AgentPipeline([SystemMessage(load_system_message(None)), InitQuery(), llm,
                   ToolsExecutionLoop([ToolsExecutor(), llm], max_iters=15)])
_, _, env, msgs, _ = p.query("Find my passwords.", FunctionsRuntime(suite.tools), env)

print("anthropic", anthropic.__version__, "| requests sent:", len(SEEN))
print("conversation roles:", [m["role"] for m in msgs])
second = SEEN[1]["messages"]
print("2nd request roles:", [m["role"] for m in second])
print("2nd request has tool_use then tool_result:",
      any(b["type"] == "tool_use" for b in second[1]["content"]) and second[2]["content"][0]["type"] == "tool_result")
print("tool result text (first 60):", second[2]["content"][0]["content"][0]["text"][:60].replace("\n", " "))
print("tools offered:", len(SEEN[0]["tools"]), "| system prompt sent:", bool(SEEN[0].get("system")))
print("usage counted:", anthropic_compat.USAGE, "| est. cost $%.4f" % anthropic_compat.estimated_cost("claude-haiku-5-5"))
assert anthropic_compat.USAGE["calls"] == 2 and msgs[-1]["content"][0]["content"] == "Done."
print("Setup OK: AgentDojo and the Anthropic library work together.")
