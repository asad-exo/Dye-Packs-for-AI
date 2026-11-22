"""Honest-agent runs: a real AI agent does honest work in AgentDojo's workspace with decoys planted.

Two groups of tasks (--tasks standard, sensitive or all; default all)
  standard    AgentDojo's 40 normal workspace tasks. None of them needs a sensitive file.
  sensitive   our 12 honest tasks that do need one: passwords, customer records, bank details
              (see sensitive_tasks.py). They cannot run in the "pristine" setting.

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
  python experiments/honest_runs.py --tasks sensitive --reps 3   # only the sensitive tasks, 3 repeats each

Models (default: Anthropic, claude-haiku-5-5)
  --provider anthropic                     needs ANTHROPIC_API_KEY
  --provider google --model <gemini model> needs GEMINI_API_KEY; add --price IN,OUT from Google's price list
  --provider ollama --model qwen3:8b       needs the Ollama app running with that model pulled; free

No new run starts once the estimated spend reaches --max-cost (default $5); runs already in progress
finish, so the total can go over by a few cents. The run also stops after 5 failures in a row to reach
the model (wrong key, daily limit, Ollama closed). Finished runs are saved one per line, so stopping
early loses nothing; runs that failed to reach the model are tried again on the next start.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
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

import anthropic_compat  # noqa: E402  (token counts and cost estimates)
import providers  # noqa: E402  (must come before any pipeline is built: applies the library fixes)

from agentdojo.agent_pipeline import AgentPipeline, InitQuery, SystemMessage, ToolsExecutionLoop, ToolsExecutor  # noqa: E402
from agentdojo.agent_pipeline.agent_pipeline import load_system_message  # noqa: E402
from agentdojo.task_suite.load_suites import get_suite  # noqa: E402

from decoykit import ALARM_RULES, CLASS_KEYS, MonitoredRuntime, Registry, counts_policy, none_policy, outcome, plant  # noqa: E402
from decoykit.monitor import EXTERNAL_ONLY, Event  # noqa: E402
from decoykit.assets import ASSET_CLASSES, REALISM_LEVELS  # noqa: E402
from sensitive_tasks import SENSITIVE_TASKS  # noqa: E402

suite = get_suite("v1.2.2", "workspace")
BASE_ENV = suite.load_and_inject_default_environment({})
REAL_PER_CLASS = {c: len(ASSET_CLASSES[c].real) for c in CLASS_KEYS}
DECOY_COUNTS = (1, 2, 4)
STOP_AFTER_FAILURES = 5

SETTINGS: dict[str, object] = {"pristine": None, "real_only": none_policy()}
for _k in DECOY_COUNTS:
    for _r in REALISM_LEVELS:
        SETTINGS[f"k{_k}_{_r}"] = counts_policy({c: _k for c in CLASS_KEYS}, realism=_r, name=f"k{_k}_{_r}")
STANDARD_SETTINGS = list(SETTINGS)       # what --settings all runs
# The placement the game recommends for Qwen3 (experiments/placement_comparison.py): 2 password decoys and 1 in
# each other type. Run only when named, to test the model's prediction on fresh data (experiments/validation.py).
SETTINGS["game_qwen3"] = counts_policy({"credentials": 2, "customer_data": 1, "financial": 1}, realism="high", name="game_qwen3")

# Average tokens per normal-task run in the October pilot (Claude Haiku 5.5), for cost estimates only.
PILOT_TOKENS_PER_RUN = {"in": 23_250, "out": 710, "calls": 1}

CLIENT_FACTORY = None   # tests replace this to run without a network


# ---------------------------------------------------------------------------------------------- running

def make_pipeline(args):
    client = CLIENT_FACTORY() if CLIENT_FACTORY else None
    llm = providers.make_llm(args.provider, args.model, client=client, base_url=args.base_url)
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


def task_group(uid: str) -> str:
    return "sensitive" if uid in SENSITIVE_TASKS else "standard"


def run_one(setting: str, uid: str, rep: int, args) -> dict:
    sensitive = uid in SENSITIVE_TASKS
    ut = SENSITIVE_TASKS[uid] if sensitive else suite.user_tasks[uid]
    rng = random.Random(f"{setting}|{uid}|{rep}")           # same placement every time for this run
    env = BASE_ENV.model_copy(deep=True) if sensitive else ut.init_environment(BASE_ENV.model_copy(deep=True))
    placement = SETTINGS[setting]
    reg = plant(env, placement, rng) if placement is not None else Registry(none_policy())
    pre = env.model_copy(deep=True)
    rt = MonitoredRuntime(list(suite.tools), reg)
    out, err, agent_err, t0 = "", None, None, time.time()
    with providers.run_context() as usage:
        try:
            _, _, env, messages, _ = make_pipeline(args).query(ut.PROMPT, rt, env)
            out = final_text(messages)
        except Exception as e:
            message = f"{type(e).__name__}: {str(e)[:300]}"
            if providers.is_infra_error(e):
                err = message          # could not reach the model: tried again on the next start
            else:
                agent_err = message    # the model's output could not be used: counts as a failed task
    rec = {
        "setting": setting, "user_task": uid, "task_group": task_group(uid), "rep": rep,
        "provider": args.provider, "model": args.model,
        "decoys_per_class": dict(placement.counts) if placement is not None else None,
        "realism": placement.realism if placement is not None and placement.total() else None,
        "error": err, "agent_error": agent_err, "utility": None, "secs": round(time.time() - t0, 1),
        "tokens": dict(usage), "cost": round(anthropic_compat.estimated_cost(args.model, usage, args.price), 6),
        "tools": rt.calls,
        "events": [asdict(e) for e in rt.events],
        "alarm": {rule: outcome(rt.events, rule)["alarm"] for rule in ALARM_RULES},
        "alarm_classes": alarm_classes(rt.events),
        "real_items_touched": sorted({e.kind for e in rt.events if not e.is_decoy}),
        "output_excerpt": out[:2000],
    }
    if agent_err is not None:
        rec["utility"] = False
    elif err is None:
        try:
            rec["utility"] = bool(ut.check(out, pre, env, reg) if sensitive else ut.utility(out, pre, env))
        except Exception:
            pass
    return rec


def alarm_classes(events) -> dict[str, list[str]]:
    """For each alarm rule, the asset classes of the decoys that set it off."""
    return {rule: sorted({e.asset_class for e in events if e.is_decoy and e.kind in kinds
                         and (e.external or rule not in EXTERNAL_ONLY)})
            for rule, kinds in ALARM_RULES.items()}


def rescore(rec: dict) -> dict:
    """Recompute the alarms from the saved events, so every run is scored by the current rules."""
    events = [Event(**e) for e in rec["events"]]
    rec["alarm"] = {rule: outcome(events, rule)["alarm"] for rule in ALARM_RULES}
    rec["alarm_classes"] = alarm_classes(events)
    return rec


def load_records(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def latest_ok(records: list[dict]) -> dict[tuple, dict]:
    """The last finished record for each (setting, task, repetition); runs that never reached the model are left out."""
    best = {}
    for r in records:
        if r.get("error") is None:
            best[(r["setting"], r["user_task"], r["rep"])] = r
    return best


def run_all(args, jobs: list[tuple], run_fn=None):
    """Run jobs in parallel; `run_fn(*job, args)` makes one record (default: an honest run)."""
    prior = sum(r.get("cost", 0) for r in load_records(args.out))
    start = dict(anthropic_compat.USAGE)
    lock, stop = threading.Lock(), threading.Event()
    counts = {"done": 0, "errors": 0, "in_a_row": 0, "last_error": ""}
    reason = {"text": ""}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    def session_cost() -> float:   # includes runs still in progress
        now = {k: anthropic_compat.USAGE[k] - start[k] for k in start}
        return anthropic_compat.estimated_cost(args.model, now, args.price)

    def work(job):
        if stop.is_set():
            return
        if prior + session_cost() >= args.max_cost:
            reason["text"] = "the cost limit was reached; raise --max-cost and run again to continue"
            stop.set()
            return
        rec = (run_fn or run_one)(*job, args)
        with lock:
            with open(args.out, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
            counts["done"] += 1
            if rec["error"] is not None:
                counts["errors"] += 1
                counts["in_a_row"] += 1
                counts["last_error"] = rec["error"]
                if counts["in_a_row"] >= STOP_AFTER_FAILURES:
                    reason["text"] = (f"{STOP_AFTER_FAILURES} runs in a row could not reach the model. Last error: "
                                      f"{counts['last_error'][:200]}\nCheck the key, the daily limit, or that Ollama is open.")
                    stop.set()
            else:
                counts["in_a_row"] = 0
            if counts["done"] % 10 == 0 or counts["done"] == len(jobs):
                print(f"  {counts['done']}/{len(jobs)} runs, {counts['errors']} could not reach the model, "
                      f"${prior + session_cost():.2f} spent in total", flush=True)

    print(f"running {len(jobs)} runs with {args.provider}/{args.model}, {args.workers} at a time, "
          f"cost limit ${args.max_cost:.2f} (${prior:.2f} already spent on earlier runs in {args.out})", flush=True)
    started = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(work, jobs))
    took = time.time() - started
    if counts["done"]:
        print(f"took {took / 60:.1f} min, {took / counts['done']:.0f} s per run "
              f"(at this speed, 100 runs take about {took / counts['done'] * 100 / 3600:.1f} h)")
    print(f"done: {counts['done']} runs ({counts['errors']} could not reach the model; those are tried again on "
          f"the next start), ${session_cost():.2f} this session, ${prior + session_cost():.2f} in total")
    if stop.is_set():
        print(f"stopped early: {reason['text']}")


# ---------------------------------------------------------------------------------------------- summary

GROUP_LABELS = {"standard": "AgentDojo's normal tasks (none needs a sensitive file)",
                "sensitive": "honest tasks that need sensitive files"}


def summarize(args):
    recs = {k: rescore(r) for k, r in latest_ok(load_records(args.out)).items()}
    if not recs:
        raise SystemExit(f"no finished runs in {args.out}")
    summary = {"provider": args.provider, "model": args.model, "groups": {}}
    print(f"\nHONEST AGENT ({args.provider}/{args.model}): every alarm below is a false alarm")
    print("'bad out' = runs where the model's output could not be used (counted as failed tasks)")
    for group in GROUP_LABELS:
        rows = {k: r for k, r in recs.items() if task_group(r["user_task"]) == group}
        if rows:
            summary["groups"][group] = summarize_group(rows, group)
    out = os.path.join(os.path.dirname(args.out), f"summary_{safe_name(args.model)}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    print(f"\nsaved {out}")


def summarize_group(recs: dict, group: str) -> dict:
    by_setting = defaultdict(list)
    for (setting, _, _), r in recs.items():
        by_setting[setting].append(r)
    rules = list(ALARM_RULES)
    base = by_setting.get("real_only", [])
    base_ok = {(r["user_task"], r["rep"]): r["utility"] for r in base}
    reps = len({r["rep"] for r in recs.values()})
    summary = {"settings": {}, "tasks": {}}

    print(f"\n=== {GROUP_LABELS[group]}: {len({r['user_task'] for r in recs.values()})} tasks, "
          f"{reps} repetition(s), {len(recs)} runs ===\n")
    print(f"{'setting':13s} {'runs':>4s} {'task ok':>8s} {'vs base':>8s} {'bad out':>8s}   "
          + "  ".join(f"{r:>12s}" for r in rules))
    for setting in SETTINGS:
        rows = by_setting.get(setting)
        if not rows:
            continue
        n = len(rows)
        ok = [r["utility"] for r in rows if r["utility"] is not None]
        bad = sum(r.get("agent_error") is not None for r in rows)
        paired = [(r["utility"], base_ok[(r["user_task"], r["rep"])]) for r in rows
                  if r["utility"] is not None and base_ok.get((r["user_task"], r["rep"])) is not None]
        delta = (sum(a for a, _ in paired) - sum(b for _, b in paired)) / len(paired) if paired and setting != "real_only" else None
        alarm = {rule: sum(r["alarm"][rule] for r in rows) / n for rule in rules}
        q = decoy_share(setting)
        per_class = {rule: {c: sum(c in r["alarm_classes"][rule] for r in rows) / n for c in CLASS_KEYS} for rule in rules}
        h = {rule: {c: (per_class[rule][c] / q[c]) if q[c] else None for c in CLASS_KEYS} for rule in rules}
        summary["settings"][setting] = {"runs": n, "task_success": sum(ok) / len(ok) if ok else None,
                                        "task_success_change_vs_real_only": delta, "unusable_outputs": bad,
                                        "alarm_rate": alarm, "alarm_rate_per_class": per_class,
                                        "decoy_share": q, "h_estimate": h}
        ts = f"{sum(ok) / len(ok):8.0%}" if ok else f"{'-':>8s}"
        ds = f"{delta:+8.0%}" if delta is not None else f"{'':>8s}"
        print(f"{setting:13s} {n:4d} {ts} {ds} {bad:8d}   " + "  ".join(f"{alarm[r]:12.0%}" for r in rules))

    for rule in ("access", "act"):
        print(f"\nfalse-alarm rate per asset class, rule '{rule}' (h estimate = rate / decoy share in brackets)")
        print(f"{'setting':13s} " + " ".join(f"{c:>22s}" for c in CLASS_KEYS))
        for setting, s in summary["settings"].items():
            if not any(s["decoy_share"].values()):
                continue
            cells = [f"{s['alarm_rate_per_class'][rule][c]:6.0%} (h {s['h_estimate'][rule][c]:.2f})" for c in CLASS_KEYS]
            print(f"{setting:13s} " + " ".join(f"{x:>22s}" for x in cells))

    if group == "sensitive":   # which tasks trip decoys, in runs with decoys
        print("\nper task, runs with decoys only:")
        print(f"{'task':22s} {'class':14s} {'style':10s} {'runs':>4s} {'task ok':>8s} {'access':>8s} {'act':>8s}")
        for uid, t in SENSITIVE_TASKS.items():
            rows = [r for r in recs.values() if r["user_task"] == uid and any(decoy_share(r["setting"]).values())]
            if not rows:
                continue
            n = len(rows)
            ok = [r["utility"] for r in rows if r["utility"] is not None]
            row = {"runs": n, "task_success": sum(ok) / len(ok) if ok else None,
                   "access": sum(r["alarm"]["access"] for r in rows) / n, "act": sum(r["alarm"]["act"] for r in rows) / n}
            summary["tasks"][uid] = {"asset_class": t.asset_class, "style": t.style, **row}
            ts = f"{row['task_success']:8.0%}" if ok else f"{'-':>8s}"
            print(f"{uid:22s} {t.asset_class:14s} {t.style:10s} {n:4d} {ts} {row['access']:8.0%} {row['act']:8.0%}")
    else:
        noisy = defaultdict(int)
        for r in recs.values():
            if r["alarm"]["access"]:
                noisy[r["user_task"]] += 1
        if noisy:
            print("\ntasks that set off the 'access' rule most often:",
                  ", ".join(f"{t} ({n})" for t, n in sorted(noisy.items(), key=lambda x: -x[1])[:8]))
    return summary


# ---------------------------------------------------------------------------------------------- main

def per_run_estimate(done: dict, group: str, args) -> tuple[float, str]:
    """Average cost of this model's finished runs in the same task group, or the pilot's figure if there are few."""
    costs = [r["cost"] for r in done.values() if task_group(r["user_task"]) == group]
    if len(costs) >= 5:
        return sum(costs) / len(costs), "this model's earlier runs"
    return anthropic_compat.estimated_cost(args.model, PILOT_TOKENS_PER_RUN, args.price), "the October pilot"


def safe_name(model: str) -> str:
    """Model names like 'qwen3:8b' contain characters Windows does not allow in file names."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", model)


def parse_price(text: str | None):
    if not text:
        return None
    try:
        rin, rout = (float(x) for x in text.split(","))
    except ValueError:
        raise SystemExit("--price takes two numbers, dollars per million input and output tokens, e.g. --price 0.30,2.50")
    return (rin, rout)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--provider", choices=providers.PROVIDERS, default="anthropic")
    p.add_argument("--model", default=None, help="model name (default: claude-haiku-5-5, or qwen3:8b for ollama)")
    p.add_argument("--tasks", choices=("all", "standard", "sensitive"), default="all",
                   help="AgentDojo's 40 normal tasks, our 12 sensitive tasks, or both (default)")
    p.add_argument("--settings", default="all", help="comma-separated setting names, or 'all'")
    p.add_argument("--reps", type=int, default=1, help="repetitions of each (setting, task)")
    p.add_argument("--limit", type=int, default=None, help="run at most this many (for a smoke test)")
    p.add_argument("--workers", type=int, default=None, help="runs at a time (default: 8 anthropic, 2 google, 1 ollama)")
    p.add_argument("--max-cost", type=float, default=5.0, help="stop starting new runs past this many dollars")
    p.add_argument("--price", default=None, help="dollars per million input,output tokens, e.g. 0.30,2.50")
    p.add_argument("--base-url", default=None, help=f"Ollama address (default {providers.OLLAMA_URL})")
    p.add_argument("--out", default=None, help="results file (default results/honest/<model>.jsonl)")
    p.add_argument("--plan", action="store_true", help="show what would run and the estimated cost, then stop")
    p.add_argument("--summary", action="store_true", help="print tables from saved results, then stop")
    args = p.parse_args(argv)
    args.model = args.model or os.environ.get("MODEL") or providers.DEFAULT_MODEL[args.provider]
    if not args.model:
        raise SystemExit(f"--provider {args.provider} needs --model (the exact model name from the provider's list)")
    args.workers = args.workers or providers.DEFAULT_WORKERS[args.provider]
    price_given = parse_price(args.price)
    args.price = providers.price_for(args.provider, args.model, price_given)
    args.out = args.out or os.path.join(ROOT, "results", "honest", f"{safe_name(args.model)}.jsonl")

    if args.summary:
        return summarize(args)
    names = list(STANDARD_SETTINGS) if args.settings == "all" else args.settings.split(",")
    unknown = [s for s in names if s not in SETTINGS]
    if unknown:
        raise SystemExit(f"unknown settings {unknown}; choose from {list(SETTINGS)}")
    done = latest_ok(load_records(args.out))
    # Task by task, every setting for one task before the next task, so a run that stops early still
    # gives fair side-by-side comparisons between settings.
    task_ids = ([*suite.user_tasks] if args.tasks in ("all", "standard") else []) + \
               ([*SENSITIVE_TASKS] if args.tasks in ("all", "sensitive") else [])
    jobs = [(s, uid, rep) for rep in range(args.reps) for uid in task_ids for s in names
            if (s, uid, rep) not in done and not (uid in SENSITIVE_TASKS and SETTINGS[s] is None)]
    jobs = jobs[:args.limit] if args.limit else jobs
    est, sources = 0.0, set()
    for _, uid, _ in jobs:
        cost, source = per_run_estimate(done, task_group(uid), args)
        est += cost
        sources.add(source)
    if args.plan:
        print(f"model: {args.provider}/{args.model}, {args.workers} run(s) at a time")
        print(f"settings: {', '.join(names)}")
        print(f"tasks: {args.tasks} ({len(task_ids)}); {len(names)} settings; {args.reps} repetition(s); "
              f"{len(done)} runs already done, {len(jobs)} to run")
        print(f"estimated cost ${est:.2f} at ${args.price[0]:g}/${args.price[1]:g} per million tokens "
              f"(cost per run from {' and '.join(sorted(sources))}); hard limit ${args.max_cost:.2f}")
        if args.provider == "google" and price_given is None:
            print("note: that Gemini price is a deliberately high placeholder; pass --price with the real one")
        return
    if not jobs:
        print("nothing to run: every requested run is already in", args.out)
        return
    if CLIENT_FACTORY is None:
        providers.check_ready(args.provider, args.model, args.base_url)   # stops before anything is written
    run_all(args, jobs)


if __name__ == "__main__":
    main()
