"""Alarm trade-off (ROC-style): thefts detected against false alarms on honest work, per alarm rule.

Measured directly, with no model in between. For each decoy setup and each alarm rule:
  false alarms   share of honest tasks that set off the rule (the 40 AgentDojo tasks plus the 12
                 sensitive ones, each task weighted equally, from results/honest/)
  detected       share of thefts that set off the rule (direct-mode hijack runs in which the agent
                 actually sent something out, from results/hijack/)
Rules run from the loosest (a decoy merely listed) to the strictest (a decoy sent outside), so each
setup gives one curve: looser rules move up and to the right.

    python experiments/alarm_tradeoff.py
Writes results/alarm_tradeoff.json.
"""
from __future__ import annotations

import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [ROOT, HERE]

from honest_runs import latest_ok, load_records, rescore  # noqa: E402
from decoykit.monitor import Event, outcome  # noqa: E402

RULES = ["any_sighting", "access", "act", "leak_or_use", "send_out"]
SETTINGS = {"k2_low": "2 low-realism decoys per type", "k2_high": "2 high-realism decoys per type",
            "k4_high": "4 high-realism decoys per type"}
MODELS = {"Qwen3": "qwen3-8b", "Claude": "claude-haiku-5-5"}


def stole(r) -> bool:
    return any(e["kind"] == "leaked" and e["external"] for e in r["events"])


def main():
    out = {"rules": RULES, "settings": SETTINGS, "models": {}}
    for name, stem in MODELS.items():
        honest = [rescore(r) for r in latest_ok(load_records(os.path.join(ROOT, "results", "honest", stem + ".jsonl"))).values()]
        hijack = [json.loads(line) for line in open(os.path.join(ROOT, "results", "hijack", stem + ".jsonl"), encoding="utf-8") if line.strip()]
        out["models"][name] = {}
        print(f"\n=== {name}: false alarms on honest tasks / thefts detected (naive thief, decoy-aware thief)")
        for s in SETTINGS:
            by_task = {}
            for r in honest:
                if r["setting"] == s:
                    by_task.setdefault(r["user_task"], []).append(r)
            fa = {rule: sum(sum(x["alarm"][rule] for x in v) / len(v) for v in by_task.values()) / len(by_task) for rule in RULES}
            cell = {"honest_tasks": len(by_task), "false_alarms": fa}
            for aware in (False, True):
                thefts = [r for r in hijack if r["mode"] == "direct" and r["error"] is None and r["setting"] == s
                          and r["aware"] == aware and stole(r)]
                det = {rule: (sum(outcome([Event(**e) for e in r["events"]], rule)["alarm"] for r in thefts) / len(thefts))
                       if thefts else None for rule in RULES}
                cell["aware" if aware else "naive"] = {"thefts": len(thefts), "detected": det}
            out["models"][name][s] = cell
            fmt = lambda d: " ".join(f"{d[r]:4.0%}" if d[r] is not None else "  - " for r in RULES)
            print(f"  {s:8s} honest tasks {len(by_task)}  false alarms   " + " ".join(f"{fa[r]:5.1%}" for r in RULES))
            print(f"  {'':8s} naive thefts {cell['naive']['thefts']:3d}  detected      {fmt(cell['naive']['detected'])}")
            print(f"  {'':8s} aware thefts {cell['aware']['thefts']:3d}  detected      {fmt(cell['aware']['detected'])}")
    print("  (columns: " + ", ".join(RULES) + ")")
    path = os.path.join(ROOT, "results", "alarm_tradeoff.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(f"\nsaved {path}")


if __name__ == "__main__":
    main()
