"""Makes AgentDojo 0.1.35 work with current versions of the Anthropic library.

AgentDojo's Anthropic adapter was written for an older Anthropic library, and two things broke since:

1. It sends requests through `client.messages.stream(...)` with a `temperature` argument, which
   the newer library rejects (found in October 2026). We replace the request function with a plain,
   non-streaming `client.messages.create(...)` without `temperature`.
2. From version 2 of the library, `MessageParam` is a Union of message types, which cannot be
   called like a class. AgentDojo calls `MessageParam(content=..., role=...)`. These types are plain
   dicts at runtime, so we swap in `dict`, which builds exactly the same object (found November 2026).

Import this module once, before building any AgentDojo pipeline (scripts in `experiments/` and its
subfolders put `experiments/` on the import path first):

    import anthropic_compat
    anthropic_compat.USAGE                          # running token counts across all requests
    with anthropic_compat.track_usage() as run:     # token counts for one agent run (per thread)
        pipeline.query(...)

Nothing here reads or stores the API key.
"""
from __future__ import annotations

import contextlib
import contextvars
import threading
import typing

from anthropic import NOT_GIVEN

import agentdojo.agent_pipeline.llms.anthropic_llm as allm

USAGE = {"in": 0, "out": 0, "calls": 0}
_LOCK = threading.Lock()
_RUN: contextvars.ContextVar[dict | None] = contextvars.ContextVar("dye_packs_run_usage", default=None)
MAX_TOKENS_CAP = 4096


@contextlib.contextmanager
def track_usage():
    """Count the tokens of the requests made inside this block, in this thread only."""
    counts = {"in": 0, "out": 0, "calls": 0}
    token = _RUN.set(counts)
    try:
        yield counts
    finally:
        _RUN.reset(token)


def count(tokens_in: int, tokens_out: int) -> None:
    """Add one model call's tokens to the running totals (used for every provider, see providers.py)."""
    run = _RUN.get()
    with _LOCK:
        for counts in (USAGE, run) if run is not None else (USAGE,):
            counts["in"] += tokens_in
            counts["out"] += tokens_out
            counts["calls"] += 1


async def _request(client, model, messages, tools, max_tokens, system_prompt=None, temperature=0.0,
                   thinking_budget_tokens=None):
    r = await client.messages.create(model=model, messages=messages, tools=tools or NOT_GIVEN,
                                     max_tokens=min(max_tokens, MAX_TOKENS_CAP), system=system_prompt or NOT_GIVEN)
    count(r.usage.input_tokens, r.usage.output_tokens)
    return r


allm.chat_completion_request = _request
if typing.get_origin(allm.MessageParam) is typing.Union:
    allm.MessageParam = dict

# Price per million tokens (input, output), for cost estimates only.
PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-haiku-4-5": (1.0, 5.0)}


def estimated_cost(model: str, counts: dict | None = None, price: tuple[float, float] | None = None) -> float:
    """Dollar estimate for the given token counts (default: everything so far). `price` is dollars per
    million input and output tokens; without it, unknown models are priced high on purpose, so a cost
    limit errs on the safe side."""
    counts = USAGE if counts is None else counts
    rin, rout = price if price is not None else PRICES.get(model, (1.0, 5.0))
    return counts["in"] / 1e6 * rin + counts["out"] / 1e6 * rout
