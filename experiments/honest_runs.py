"""Honest-agent runs: a real AI agent does AgentDojo's 40 normal workspace tasks with decoys planted.

Nobody is attacking here, so every alarm is a false alarm. This measures, for each decoy setting:
  - how often each alarm rule fires (overall and per asset class), which gives the h values the solver needs
  - whether the decoys hurt task success, compared with the same workspace without decoys

Settings
  pristine          AgentDojo's workspace as shipped: nothing planted
  real_only         our real (synthetic) secrets planted, no decoys: the baseline for task success
  k{1,2,4}_{realism}  k decoys per asset class at low / medium / high realism, plus the real secrets.
                    With 2 real items per class, k = 1, 2, 4 means decoy shares of 1/3, 1/2 and 2/3.

Usage (from the repository's top folder)
  python experiments/honest_runs.py --plan             # what would run and the estimated cost; spends nothing
  python experiments/honest_runs.py --limit 5          # smoke test: the first 5 runs only
  python experiments/honest_runs.py                    # all runs; safe to stop and restart, it resumes
  python experiments/honest_runs.py --summary          # tables from the saved results; spends nothing

Running needs the ANTHROPIC_API_KEY environment variable (see README.md). No new run starts once the
estimated spend reaches --max-cost (default $5); runs already in progress finish, so the total can go
over by a few cents. Finished runs are saved one per line, so stopping early loses nothing.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import threading
import time
import warnings
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [ROOT, HERE]

import anthropic_compat  # noqa: E402  (must come before the pipeline is built)

import anthropic  # noqa: E402
import agentdojo.agent_pipeline.llms.anthropic_llm as allm  # noqa: E402
from agentdojo.agent_pipeline import AgentPipeline, InitQuery, SystemMessage, ToolsExecutionLoop, ToolsExecutor  # noqa: E402
from agentdojo.agent_pipeline.agent_pipeline import load_system_message  # noqa: E402
from agentdojo.task_suite.load_suites import get_suite  # noqa: E402

from decoykit import ALARM_RULES, CLASS_KEYS, MonitoredRuntime, Registry, counts_policy, none_policy, outcome, plant  # noqa: E402
from decoykit.assets import ASSET_CLASSES, REALISM_LEVELS  # noqa: E402

suite = get_suite("v1.2.2", "workspace")
BASE_ENV = suite.load_and_inject_default_environment({})
REAL_PER_CLASS = {c: len(ASSET_CLASSES[c].real) for c in CLASS_KEYS}
DECOY_COUNTS = (1, 2, 4)

SETTINGS: dict[str, object] = {"pristine": None, "real_only": none_policy()}
for _k in DECOY_COUNTS:
    for _r in REALISM_LEVELS:
        SETTINGS[f"k{_k}_{_r}"] = counts_policy({c: _k for c in CLASS_KEYS}, realism=_r, name=f"k{_k}_{_r}")

# Average tokens per normal-task run in the October pilot (Claude Haiku 5.5), for cost estimates only.
PILOT_TOKENS_PER_RUN = {"in": 23_250, "out": 710, "calls": 1}


# ---------------------------------------------------------------------------------------------- running

def make_client():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise SystemExit("Set the ANTHROPIC_API_KEY environment variable first (see README.md).")
    return anthropic.AsyncAnthropic(api_key=key, max_retries=6)


def make_pipeline(model: str):
    llm = allm.AnthropicLLM(make_client(), model)
    return AgentPipeline([SystemMessage(load_system_message(None)), InitQuery(), llm,
                          ToolsExecutionLoop([ToolsExecutor(), llm], max_iters=15)])


def final_text(messages) -> str:
    for m in reversed(messages):
        if m["role"] == "assistant" and m.get("content"):
            return "".join(b.get("content", "") or "" for b in m["content"])
    return ""


def decoy_share(setting: str) -> dict[str, float]:
    placement = SETTINGS[setting]
    if placement is None:
        return {c: 0.0 for c in CLASS_KEYS}
    return {c: placement.counts[c] / (placement.counts[c] + REAL_PER_CLASS[c]) for c in CLASS_KEYS}


def run_one(setting: str, uid: str, rep: int, model: str) -> dict:
    ut = suite.user_tasks[uid]
    rng = random.Random(f"{setting}|{uid}|{rep}")           # same placement every time for this run
    env = ut.init_environment(BASE_ENV.model_copy(deep=True))
    placement = SETTINGS[setting]
    reg = plant(env, placement, rng) if placement is not None else Registry(none_policy())
    pre = env.model_copy(deep=True)
    rt = MonitoredRuntime(list(suite.tools), reg)
    out, err, t0 = "", None, time.time()
    with anthropic_compat.track_usage() as usage:
        try:
            _, _, env, messages, _ = make_pipeline(model).query(ut.PROMPT, rt, env)
            out = final_text(messages)
        except Exception as e:  # keep going; the run is retried on the next start
            err = f"{type(e).__name__}: {str(e)[:300]}"
    rec = {
        "setting": setting, "user_task": uid, "rep": rep, "model": model,
        "decoys_per_class": dict(placement.counts) if placement is not None else None,
        "realism": placement.realism if placement is not None and placement.total() else None,
        "error": err, "utility": None, "secs": round(time.time() - t0, 1),
        "tokens": dict(usage), "cost": round(anthropic_compat.estimated_cost(model, usage), 6),
        "tools": rt.calls,
        "events": [asdict(e) for e in rt.events],
        "alarm": {rule: outcome(rt.events, rule)["alarm"] for rule in ALARM_RULES},
        "alarm_classes": {rule: sorted({e.asset_class for e in rt.events if e.is_decoy and e.kind in kinds})
                          for rule, kinds in ALARM_RULES.items()},
        "real_items_touched": sorted({e.kind for e in rt.events if not e.is_decoy}),
        "output_excerpt": out[:300],
    }
    if err is None:
        try:
            rec["utility"] = bool(ut.utility(out, pre, env))
        except Exception:
            pass
    return rec


def load_records(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def latest_ok(records: list[dict]) -> dict[tuple, dict]:
    """The last error-free record for each (setting, task, repetition)."""
    best = {}
    for r in records:
        if r.get("error") is None:
            best[(r["setting"], r["user_task"], r["rep"])] = r
    return best


def run_all(args, jobs: list[tuple]):
    prior = sum(r.get("cost", 0) for r in load_records(args.out))
    start = dict(anthropic_compat.USAGE)
    lock, stop = threading.Lock(), threading.Event()
    counts = {"done": 0, "errors": 0}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    def session_cost() -> float:   # includes runs still in progress
        now = {k: anthropic_compat.USAGE[k] - start[k] for k in start}
        return anthropic_compat.estimated_cost(args.model, now)

    def work(job):
        if stop.is_set() or prior + session_cost() >= args.max_cost:
            stop.set()
            return
        rec = run_one(*job, args.model)
        with lock:
            with open(args.out, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
            counts["done"] += 1
            counts["errors"] += rec["error"] is not None
            if counts["done"] % 10 == 0 or counts["done"] == len(jobs):
                print(f"  {counts['done']}/{len(jobs)} runs, {counts['errors']} errors, "
                      f"${prior + session_cost():.2f} spent in total", flush=True)

    print(f"running {len(jobs)} runs with {args.model}, {args.workers} at a time, cost limit ${args.max_cost:.2f} "
          f"(${prior:.2f} already spent on earlier runs in {args.out})", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(work, jobs))
    left = len(jobs) - counts["done"]
    print(f"done: {counts['done']} runs ({counts['errors']} errors, retried on the next start), "
          f"${session_cost():.2f} this session, ${prior + session_cost():.2f} in total")
    if stop.is_set() and left:
        print(f"stopped at the cost limit with {left} runs left; raise --max-cost and run again to continue")


# ---------------------------------------------------------------------------------------------- summary

def summarize(args):
    recs = latest_ok(load_records(args.out))
    if not recs:
        raise SystemExit(f"no finished runs in {args.out}")
    by_setting = defaultdict(list)
    for (setting, _, _), r in recs.items():
        by_setting[setting].append(r)
    rules = list(ALARM_RULES)
    base = by_setting.get("real_only", [])
    base_ok = {(r["user_task"], r["rep"]): r["utility"] for r in base}
    summary = {"model": args.model, "settings": {}}

    print(f"\nHONEST AGENT ({args.model}): every alarm below is a false alarm\n")
    print(f"{'setting':13s} {'runs':>4s} {'task ok':>8s} {'vs base':>8s}   " + "  ".join(f"{r:>12s}" for r in rules))
    for setting in SETTINGS:
        rows = by_setting.get(setting)
        if not rows:
            continue
        n = len(rows)
        ok = [r["utility"] for r in rows if r["utility"] is not None]
        paired = [(r["utility"], base_ok[(r["user_task"], r["rep"])]) for r in rows
                  if r["utility"] is not None and base_ok.get((r["user_task"], r["rep"])) is not None]
        delta = (sum(a for a, _ in paired) - sum(b for _, b in paired)) / len(paired) if paired and setting != "real_only" else None
        alarm = {rule: sum(r["alarm"][rule] for r in rows) / n for rule in rules}
        q = decoy_share(setting)
        per_class = {rule: {c: sum(c in r["alarm_classes"][rule] for r in rows) / n for c in CLASS_KEYS} for rule in rules}
        h = {rule: {c: (per_class[rule][c] / q[c]) if q[c] else None for c in CLASS_KEYS} for rule in rules}
        summary["settings"][setting] = {"runs": n, "task_success": sum(ok) / len(ok) if ok else None,
                                        "task_success_change_vs_real_only": delta, "alarm_rate": alarm,
                                        "alarm_rate_per_class": per_class, "decoy_share": q, "h_estimate": h}
        ts = f"{sum(ok) / len(ok):8.0%}" if ok else f"{'-':>8s}"
        ds = f"{delta:+8.0%}" if delta is not None else f"{'':>8s}"
        print(f"{setting:13s} {n:4d} {ts} {ds}   " + "  ".join(f"{alarm[r]:12.0%}" for r in rules))

    for rule in ("access", "act"):
        print(f"\nfalse-alarm rate per asset class, rule '{rule}' (h estimate = rate / decoy share in brackets)")
        print(f"{'setting':13s} " + " ".join(f"{c:>22s}" for c in CLASS_KEYS))
        for setting, s in summary["settings"].items():
            if not any(s["decoy_share"].values()):
                continue
            cells = [f"{s['alarm_rate_per_class'][rule][c]:6.0%} (h {s['h_estimate'][rule][c]:.2f})" for c in CLASS_KEYS]
            print(f"{setting:13s} " + " ".join(f"{x:>22s}" for x in cells))

    noisy = defaultdict(int)
    for r in recs.values():
        if r["alarm"]["access"]:
            noisy[r["user_task"]] += 1
    if noisy:
        print("\ntasks that set off the 'access' rule most often:",
              ", ".join(f"{t} ({n})" for t, n in sorted(noisy.items(), key=lambda x: -x[1])[:8]))
    out = os.path.join(os.path.dirname(args.out), f"summary_{args.model}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    print(f"\nsaved {out}")


# ---------------------------------------------------------------------------------------------- main

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--model", default=os.environ.get("MODEL", "claude-haiku-5-5"))
    p.add_argument("--settings", default="all", help="comma-separated setting names, or 'all'")
    p.add_argument("--reps", type=int, default=1, help="repetitions of each (setting, task)")
    p.add_argument("--limit", type=int, default=None, help="run at most this many (for a smoke test)")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--max-cost", type=float, default=5.0, help="stop starting new runs past this many dollars")
    p.add_argument("--out", default=None, help="results file (default results/honest/<model>.jsonl)")
    p.add_argument("--plan", action="store_true", help="show what would run and the estimated cost, then stop")
    p.add_argument("--summary", action="store_true", help="print tables from saved results, then stop")
    args = p.parse_args(argv)
    args.out = args.out or os.path.join(ROOT, "results", "honest", f"{args.model}.jsonl")

    if args.summary:
        return summarize(args)
    names = list(SETTINGS) if args.settings == "all" else args.settings.split(",")
    unknown = [s for s in names if s not in SETTINGS]
    if unknown:
        raise SystemExit(f"unknown settings {unknown}; choose from {list(SETTINGS)}")
    done = latest_ok(load_records(args.out))
    # Task by task, every setting for one task before the next task, so a run that stops early still
    # gives fair side-by-side comparisons between settings.
    jobs = [(s, uid, rep) for rep in range(args.reps) for uid in suite.user_tasks for s in names
            if (s, uid, rep) not in done]
    jobs = jobs[:args.limit] if args.limit else jobs
    est = len(jobs) * anthropic_compat.estimated_cost(args.model, PILOT_TOKENS_PER_RUN)
    if args.plan:
        print(f"settings: {', '.join(names)}")
        print(f"{len(suite.user_tasks)} tasks x {len(names)} settings x {args.reps} repetition(s); "
              f"{len(done)} already done, {len(jobs)} to run")
        print(f"estimated cost ${est:.2f} with {args.model} (from the October pilot's tokens per run); "
              f"hard limit ${args.max_cost:.2f}")
        return
    if not jobs:
        print("nothing to run: every requested run is already in", args.out)
        return
    make_client()   # stops here, before anything is written, if the API key is missing
    run_all(args, jobs)


if __name__ == "__main__":
    main()
