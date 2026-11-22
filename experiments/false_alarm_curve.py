"""False alarms against the share of honest work that touches sensitive files, by alarm rule and decoy realism.

A company's mix of honest work decides the false-alarm cost. The runs measure two kinds of honest task: the 40
normal AgentDojo tasks, which never need the sensitive files, and the sensitive tasks (experiments/
sensitive_tasks.py), which do. For a workload in which a share f of the tasks are sensitive, the false-alarm rate
is the mix of the two measured rates:

    false alarms(f) = (1 - f) * rate on normal tasks + f * rate on sensitive tasks

Each rate is the average over tasks of the share of runs that set off the rule, pooling 1, 2 and 4 decoys per type
at the given realism (the count of decoys barely matters; README). Also reported: how often a sensitive request
that only describes its file got the wrong answer once decoys were there (the confusion cost), and each sensitive
task's own rates over all its runs with decoys.

    python experiments/false_alarm_curve.py
Writes results/false_alarm_curve.json (used by figures/charts.py).
"""
from __future__ import annotations

import json
import os
import sys
import warnings
from collections import defaultdict

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [ROOT, HERE]

from honest_runs import latest_ok, load_records, rescore  # noqa: E402
from placement_comparison import _right  # noqa: E402
from sensitive_tasks import EDIT_TASKS, SENSITIVE_TASKS  # noqa: E402

RULES = ["any_sighting", "access", "act", "send_out"]
REALISM = ["low", "medium", "high"]
MODELS = {"Claude": "claude-haiku-5-5", "Qwen3": "qwen3-8b"}


def per_task_rate(rows, rule):
    by = defaultdict(list)
    for r in rows:
        by[r["user_task"]].append(r["alarm"][rule])
    return (sum(sum(v) / len(v) for v in by.values()) / len(by)) if by else None, len(by)


def main():
    out = {"rules": RULES, "models": {}, "task_set": {}, "tasks": {}}
    for name, stem in MODELS.items():
        recs = [rescore(r) for r in latest_ok(load_records(os.path.join(ROOT, "results", "honest", stem + ".jsonl"))).values()]
        out["models"][name] = {}
        with_decoys = [r for r in recs if r["setting"] not in ("pristine", "real_only")]
        # the share of sensitive tasks among all the tasks run (the task set behind the alarm chart)
        out["task_set"][name] = {g: len({r["user_task"] for r in with_decoys if (r.get("task_group") or "standard") == g})
                                 for g in ("standard", "sensitive")}
        out["tasks"][name] = {}
        for uid in sorted({r["user_task"] for r in with_decoys if r.get("task_group") == "sensitive"}):
            rows = [r for r in with_decoys if r["user_task"] == uid]
            out["tasks"][name][uid] = {"runs": len(rows), "kind": "edit or use" if uid in EDIT_TASKS else "read or send",
                                       "style": SENSITIVE_TASKS[uid].style,
                                       **{rule: sum(r["alarm"][rule] for r in rows) / len(rows) for rule in RULES},
                                       "right": sum(map(_right, rows)) / len(rows)}
        print(f"=== {name}: false alarms on normal / sensitive tasks (share of runs, averaged over tasks)")
        for realism in REALISM:
            settings = {f"k{k}_{realism}" for k in (1, 2, 4)}
            normal = [r for r in recs if r["setting"] in settings and (r.get("task_group") or "standard") == "standard"]
            sens = [r for r in recs if r["setting"] in settings and r.get("task_group") == "sensitive"]
            if len({r["user_task"] for r in normal}) < 20 or not sens:      # too few normal tasks at this realism
                continue
            cell = {"normal_tasks": len({r["user_task"] for r in normal}), "normal_runs": len(normal),
                    "sensitive_tasks": len({r["user_task"] for r in sens}), "sensitive_runs": len(sens), "rules": {}}
            for rule in RULES:
                cell["rules"][rule] = {"normal": per_task_rate(normal, rule)[0], "sensitive": per_task_rate(sens, rule)[0]}
            described = [r for r in sens if SENSITIVE_TASKS[r["user_task"]].style == "described"]
            cell["wrong_answers_described"] = 1 - sum(map(_right, described)) / len(described) if described else None
            out["models"][name][realism] = cell
            print(f"  {realism:6s} normal {cell['normal_tasks']} tasks/{cell['normal_runs']} runs, sensitive "
                  f"{cell['sensitive_tasks']}/{cell['sensitive_runs']}: " +
                  "  ".join(f"{rule} {cell['rules'][rule]['normal']:.1%}/{cell['rules'][rule]['sensitive']:.1%}" for rule in RULES) +
                  f"  wrong answers (described) {cell['wrong_answers_described']:.0%}")
    path = os.path.join(ROOT, "results", "false_alarm_curve.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(f"saved {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    main()
