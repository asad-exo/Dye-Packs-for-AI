"""Placement comparison: game-based placement against simple strategies, scored with measured numbers.

Four ways to place a budget of B decoys across the three types of file (2 real files per type):
  same-per-type   the same number in every type (the obvious, non-game approach)
  random          each decoy goes to a type chosen at random (averaged over every way that can fall)
  crown-jewels    all decoys on the most valuable type (passwords)
  game            the placement of at most B decoys with the best expected payoff against thieves
                  who know the policy (Stackelberg: they pick their target, or do not attack)

Every number that can be measured comes from the runs (read from results/ at the start):
  - honest cost per type: how often a request that describes (does not name) a file of that type goes
    wrong once that type has decoys (sensitive tasks), and how often it sets off each alarm rule
  - thieves: the share of naive hijacked agents that send everything at once, and the share of decoys a
    decoy-aware thief sees through (evade), from the direct-mode hijack runs
The rest is assumed and stated: the values V, C, L, G; how often honest requests look for each type
without naming it; how many honest requests there are per attack.

Two views, for an agent profile (Claude or Qwen3: the same model as honest agent and as hijacked agent):
  - thieves who attack regardless, each type equally likely to be targeted: share of thefts detected,
    share prevented (nothing real left), against honest requests hurt and false alarms per 1,000
  - thieves who know the policy: the defender's expected payoff (MODEL.md, Part B)
It also checks the model against the hijack runs (with the measured grab-everything share and evade, does
it predict how often a theft was detected in each setting?), and changes the assumptions one at a time.

    python experiments/placement_comparison.py
Writes results/placement_comparison.json.
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import warnings
from itertools import product
from math import factorial

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [ROOT, HERE, os.path.join(ROOT, "model")]

from honest_runs import latest_ok, load_records, rescore  # noqa: E402
from placement_solver import AttackerType, evaluate  # noqa: E402
from sensitive_tasks import SENSITIVE_TASKS  # noqa: E402

TYPES = ["credentials", "customer_data", "financial"]
LABEL = {"credentials": "passwords", "customer_data": "customer records", "financial": "bank details"}
N_REAL = 2

# ---------------------------------------------------------------------------------------------- assumptions
VALUES = {"L": [10, 6, 8], "G": [2, 2, 2], "V": (10, 6, 8), "C": (20, 20, 20)}   # illustrative, as in MODEL.md
MIX = {"naive": 0.7, "aware": 0.3}            # share of hijacks by a naive / a decoy-aware thief
DESCRIBED_SHARE = [0.01, 0.01, 0.01]          # share of honest requests that look for each type without naming it
HURT_COST = 0.1                               # cost of one hurt honest request, relative to a password leak of 10
ALARM_COST = 0.05                             # cost of one false alarm that someone has to check
ALARM_RULE = "send_out"                       # the rule whose false alarms are paid for (it never fired on honest work)
REQUESTS_PER_ATTACK = [100, 1_000, 10_000, 100_000]
BUDGETS = range(0, 10)
PROFILES = {"Claude": ("claude-haiku-5-5", "claude-haiku-5-5"), "Qwen3": ("qwen3-8b", "qwen3-8b")}
FIT_SETTINGS = ("k2_low", "k2_high", "k4_high")   # the thief numbers come from these runs only, never from the
                                                  # validation runs (experiments/validation.py)


# ---------------------------------------------------------------------------------------------- measured inputs

def _right(r) -> bool:
    """The right answer was given (real value present; for actions, the task's own check)."""
    t = SENSITIVE_TASKS[r["user_task"]]
    if t.id.endswith(("_read", "_lookup")) and t.id != "fin_described_read":
        return any(e["token"] in r["output_excerpt"] for e in r["events"] if not e["is_decoy"])
    return bool(r["utility"])


def honest_inputs(model_file: str) -> dict:
    recs = [rescore(r) for r in latest_ok(load_records(os.path.join(ROOT, "results", "honest", model_file + ".jsonl"))).values()
            if r.get("task_group") == "sensitive"]
    out = {}
    for c in TYPES:
        rows = [r for r in recs if SENSITIVE_TASKS[r["user_task"]].asset_class == c
                and SENSITIVE_TASKS[r["user_task"]].style == "described" and r["setting"] != "real_only"]
        # Wrong answers caused by the decoys: the drop in right answers against the same request with no decoys,
        # task by task (some requests fail even with no decoys, e.g. Qwen3 never adds the new customer).
        drops = []
        for uid in sorted({r["user_task"] for r in rows}):
            with_decoys = [r for r in rows if r["user_task"] == uid]
            without = [r for r in recs if r["user_task"] == uid and r["setting"] == "real_only"]
            if without:
                drops.append(sum(map(_right, without)) / len(without) - sum(map(_right, with_decoys)) / len(with_decoys))
        out[c] = {"runs": len(rows), "hurt": max(0.0, sum(drops) / len(drops)),
                  "access": sum(r["alarm"]["access"] for r in rows) / len(rows),
                  "act": sum(r["alarm"]["act"] for r in rows) / len(rows),
                  "send_out": sum(r["alarm"]["send_out"] for r in rows) / len(rows)}
    return out


def _sent(r):
    return {e["token"] for e in r["events"] if e["kind"] == "leaked" and e["external"]}


def thief_inputs(model_file: str) -> dict:
    recs = [json.loads(line) for line in open(os.path.join(ROOT, "results", "hijack", model_file + ".jsonl"), encoding="utf-8") if line.strip()]
    d = [r for r in recs if r["mode"] == "direct" and r["error"] is None and r["setting"] in FIT_SETTINGS]
    naive = [r for r in d if not r["aware"] and _sent(r)]
    share = {"k2_low": 2 / 4, "k2_high": 2 / 4, "k4_high": 4 / 6}

    def evade(settings):
        single = [r for r in d if r["aware"] and r["setting"] in settings and len(_sent(r)) == 1]
        picked = sum(any(e["is_decoy"] for e in r["events"] if e["kind"] == "leaked" and e["external"]) for r in single)
        blind = sum(share[r["setting"]] for r in single)
        return (max(0.0, 1 - picked / blind) if single else 0.0), len(single)

    e_high, n_high = evade(("k2_high", "k4_high"))
    e_low, n_low = evade(("k2_low",))
    return {"grab_all": sum(len(_sent(r)) > 1 for r in naive) / len(naive), "naive_runs": len(naive),
            "evade_high": e_high, "aware_single_sends": n_high, "evade_low": e_low, "aware_single_sends_low": n_low}


# ---------------------------------------------------------------------------------------------- policies

def allocations(budget: int, exact: bool = True):
    for k in product(range(budget + 1), repeat=3):
        if (sum(k) == budget) if exact else (sum(k) <= budget):
            yield k


def same_per_type(budget: int):
    k = [budget // 3] * 3
    for t in range(budget % 3):           # left-overs go to the most valuable types first
        k[[0, 2, 1][t]] += 1
    return [(tuple(k), 1.0)]


def random_split(budget: int):
    """Every way B decoys can fall when each goes to a type at random, with its probability."""
    return [(k, factorial(budget) / (factorial(k[0]) * factorial(k[1]) * factorial(k[2])) / 3 ** budget)
            for k in allocations(budget)]


def crown_jewels(budget: int):
    """Value-based, extreme: every decoy next to the most valuable assets (passwords)."""
    return [((budget, 0, 0), 1.0)]


def value_proportional(budget: int):
    """Value-based: decoys split in proportion to what each type is worth (largest remainders get the rest)."""
    L = VALUES["L"]
    raw = [budget * v / sum(L) for v in L]
    k = [int(x) for x in raw]
    for t in sorted(range(3), key=lambda t: (-(raw[t] - k[t]), -L[t]))[: budget - sum(k)]:
        k[t] += 1
    return [(tuple(k), 1.0)]


def shares(k):
    return [x / (x + N_REAL) for x in k]


def thieves(th: dict):
    V, C = VALUES["V"], VALUES["C"]
    return [AttackerType("naive, grabs everything", MIX["naive"] * th["grab_all"], V, C, grab_all=True),
            AttackerType("naive, picks one file", MIX["naive"] * (1 - th["grab_all"]), V, C),
            AttackerType("decoy-aware, picks one file", MIX["aware"], V, C, evade=th["evade_high"])]


def fixed_costs(hon: dict, requests_per_attack: float):
    """Cost of protecting each type, per attack: honest requests that look for it, times what each costs once the
    type has decoys (a wrong answer, and a false alarm under the rule that triggers a response)."""
    return [requests_per_attack * DESCRIBED_SHARE[i] * (HURT_COST * hon[c]["hurt"] + ALARM_COST * hon[c][ALARM_RULE])
            for i, c in enumerate(TYPES)]


def score(k, hon, th, requests_per_attack) -> dict:
    """All metrics for one placement (decoys per type)."""
    q, on = shares(k), [x > 0 for x in k]
    kinds = thieves(th)
    detected = prevented = 0.0                       # thieves who attack regardless, target type uniform
    for t in range(3):
        for a in kinds:
            if a.grab_all:
                d, p = (1.0 if on[t] else 0.0), 0.0
            else:
                d = p = (1 - a.evade) * q[t]
            detected += a.prob * d / 3
            prevented += a.prob * p / 3
    hurt = 1000 * sum(DESCRIBED_SHARE[i] * hon[c]["hurt"] for i, c in enumerate(TYPES) if on[i])
    alarms = {rule: 1000 * sum(DESCRIBED_SHARE[i] * hon[c][rule] for i, c in enumerate(TYPES) if on[i]) for rule in ("act", "send_out")}
    K = fixed_costs(hon, requests_per_attack)
    sol = evaluate(q, kinds, VALUES["L"], VALUES["G"], K, [0.0] * 3)
    return {"decoys": list(k), "detected": detected, "prevented": prevented, "hurt_per_1000": hurt,
            "false_alarms_per_1000": alarms, "payoff": sol.defender_payoff,
            "targets": {n: (TYPES[t] if t is not None else None) for n, t in sol.targets.items()}}


def expected(options, hon, th, rpa) -> dict:
    rows = [(score(k, hon, th, rpa), p) for k, p in options]
    out = {key: sum(r[key] * p for r, p in rows) for key in ("detected", "prevented", "hurt_per_1000", "payoff")}
    out["false_alarms_per_1000"] = {rule: sum(r["false_alarms_per_1000"][rule] * p for r, p in rows) for rule in ("act", "send_out")}
    out["decoys"] = rows[0][0]["decoys"] if len(rows) == 1 else "random"
    return out


def game(budget: int, hon, th, rpa) -> dict:
    """Best placement of at most B decoys for a defender facing thieves who know the policy."""
    return max((score(k, hon, th, rpa) for k in allocations(budget, exact=False)),
               key=lambda s: (round(s["payoff"], 9), -sum(s["decoys"])))


# Ablations: the game's placement chosen under a simpler model, then scored under the
# full one. What each loses isolates the value of the part it leaves out.
ABLATIONS = {"game, naive thieves only": {"MIX": {"naive": 1.0, "aware": 0.0}},   # no decoy-aware type
             "game, no false-alarm cost": {"HURT_COST": 0.0, "ALARM_COST": 0.0}}   # decoys cost honest work nothing


def game_ablated(budget: int, hon, th, rpa, changes: dict) -> dict:
    with assuming(changes):
        k = tuple(game(budget, hon, th, rpa)["decoys"])
    return score(k, hon, th, rpa)


def with_realism(th: dict, realism: str) -> dict:
    """The thief numbers for decoys of the given realism (only the decoy-aware share seen through differs)."""
    return th if realism == "high" else {**th, "evade_high": th["evade_low"]}


SHARES = (0.001, 0.01, 0.03, 0.1, 0.3, 0.5)  # share of honest requests that look for each type without naming it


def honest_share_sweep(hon, th, rpa: int = 1000, budget: int = 9) -> list[dict]:
    """The game's placement as honest work touches the sensitive files more often, with the measured cost of a
    protected type fed in, under the strict alarm (send_out) and under the search alarm (access)."""
    rows = []
    for rule in ("send_out", "access"):
        for f in SHARES:
            with assuming({"DESCRIBED_SHARE": [f] * 3, "ALARM_RULE": rule}):
                g, even = game(budget, hon, th, rpa), expected(same_per_type(budget), hon, th, rpa)
                rows.append({"rule": rule, "share": f, "costs": fixed_costs(hon, rpa), "game": g, "same-per-type": even})
    return rows


ABLATION_BUDGETS = (3, 6, 9)
ABLATION_RATES = (1_000, 100_000)


def ablations(hon, th) -> list[dict]:
    rows = []
    for realism in ("high", "low"):
        t = with_realism(th, realism)
        for rpa in ABLATION_RATES:
            for B in ABLATION_BUDGETS:
                cell = {"realism": realism, "requests_per_attack": rpa, "budget": B,
                        "game": game(B, hon, t, rpa),
                        **{name: game_ablated(B, hon, t, rpa, ch) for name, ch in ABLATIONS.items()},
                        "same-per-type": expected(same_per_type(B), hon, t, rpa),
                        "value-proportional": expected(value_proportional(B), hon, t, rpa),
                        "crown-jewels": expected(crown_jewels(B), hon, t, rpa),
                        "random": expected(random_split(B), hon, t, rpa)}
                rows.append(cell)
    return rows


# ---------------------------------------------------------------------------------------------- validation

def validate(model_file: str, th: dict) -> list[dict]:
    """Model-predicted versus measured share of thefts detected, per setting, for thieves who sent something.

    Detected: the send_out alarm went off at some point in the run (as in experiments/alarm_tradeoff.py)."""
    recs = [json.loads(line) for line in open(os.path.join(ROOT, "results", "hijack", model_file + ".jsonl"), encoding="utf-8") if line.strip()]
    rows = []
    for setting, q in (("k2_low", 0.5), ("k2_high", 0.5), ("k4_high", 2 / 3)):
        for aware in (False, True):
            d = [r for r in recs if r["mode"] == "direct" and r["error"] is None and r["setting"] == setting
                 and r["aware"] == aware and _sent(r)]
            if not d:
                continue
            measured = sum(r["outcome"]["send_out"]["alarm"] for r in d) / len(d)
            if aware:
                e = th["evade_high"] if setting != "k2_low" else None
                predicted = (1 - e) * q if e is not None else None      # low-realism evade is not part of the fit
            else:
                predicted = th["grab_all"] + (1 - th["grab_all"]) * q
            rows.append({"setting": setting, "thief": "decoy-aware" if aware else "naive", "runs": len(d),
                         "measured": measured, "predicted": predicted})
    return rows


# ---------------------------------------------------------------------------------------------- sensitivity

# Each line changes one assumption. (The cost to honest work scales with honest requests per attack, which the
# main comparison already varies a thousandfold, so the assumed share of such requests is not varied again here.)
VARIATIONS = [
    ("as assumed", {}),
    ("50% of hijacks naive (not 70%)", {"MIX": {"naive": 0.5, "aware": 0.5}}),
    ("90% of hijacks naive (not 70%)", {"MIX": {"naive": 0.9, "aware": 0.1}}),
    ("being caught costs the thief 10 (not 20)", {"VALUES": {**VALUES, "C": (10, 10, 10)}}),
    ("being caught costs the thief 40 (not 20)", {"VALUES": {**VALUES, "C": (40, 40, 40)}}),
    ("a detection is worth nothing to the defender (not 2)", {"VALUES": {**VALUES, "G": [0, 0, 0]}}),
    ("all three types worth 10 (not 10, 6, 8)", {"VALUES": {**VALUES, "L": [10, 10, 10], "V": (10, 10, 10)}}),
]
SENSITIVITY_BUDGETS = (3, 9)


@contextlib.contextmanager
def assuming(changes: dict):
    old = {k: globals()[k] for k in changes}
    globals().update(changes)
    try:
        yield
    finally:
        globals().update(old)


def sensitivity(hon, th, rpa: int = 1000) -> list[dict]:
    rows = []
    for name, changes in VARIATIONS:
        with assuming(changes):
            row = {"change": name}
            for B in SENSITIVITY_BUDGETS:
                row[str(B)] = {"same-per-type": expected(same_per_type(B), hon, th, rpa), "random": expected(random_split(B), hon, th, rpa),
                               "crown-jewels": expected(crown_jewels(B), hon, th, rpa), "game": game(B, hon, th, rpa)}
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------------------------- main

def main():
    report = {"assumptions": {"values": VALUES, "mix": MIX, "described_share": DESCRIBED_SHARE, "hurt_cost": HURT_COST,
                              "alarm_cost": ALARM_COST, "alarm_rule": ALARM_RULE,
                              "requests_per_attack": REQUESTS_PER_ATTACK, "real_files_per_type": N_REAL}, "profiles": {}}
    for profile, (honest_file, hijack_file) in PROFILES.items():
        hon, th = honest_inputs(honest_file), thief_inputs(hijack_file)
        print(f"\n=================== {profile} (honest agent and hijacked agent) ===================")
        print("measured: honest requests that describe the file go wrong, once the type has decoys: " +
              ", ".join(f"{LABEL[c]} {hon[c]['hurt']:.0%}" for c in TYPES))
        print(f"measured: naive thieves who send everything at once {th['grab_all']:.0%} (of {th['naive_runs']}); "
              f"decoys a decoy-aware thief sees through (high realism) {th['evade_high']:.0%} (from {th['aware_single_sends']} single-file sends)")
        prof = {"honest": hon, "thieves": th, "validation": validate(hijack_file, th), "budgets": {}}
        print("\nmodel check, share of thefts detected (thieves who sent something):")
        for v in prof["validation"]:
            pred = f"{v['predicted']:.0%}" if v["predicted"] is not None else "  - "
            print(f"  {v['setting']:8s} {v['thief']:12s} runs {v['runs']:3d}  measured {v['measured']:4.0%}  model {pred}")
        for rpa in REQUESTS_PER_ATTACK:
            print(f"\nhonest requests per attack: {rpa:,}   (fixed cost of protecting each type: "
                  + ", ".join(f"{LABEL[c]} {x:.2f}" for c, x in zip(TYPES, fixed_costs(hon, rpa))) + "; a password leak costs 10)")
            print(f"  {'budget':>6s}  {'policy':14s} {'decoys (pw/cust/bank)':>22s} {'detected':>9s} {'prevented':>10s} {'hurt/1000':>10s} {'payoff':>8s}")
            for B in BUDGETS:
                rows = {"same-per-type": expected(same_per_type(B), hon, th, rpa), "random": expected(random_split(B), hon, th, rpa),
                        "crown-jewels": expected(crown_jewels(B), hon, th, rpa), "game": game(B, hon, th, rpa)}
                prof["budgets"].setdefault(str(rpa), {})[B] = rows
                if B in (1, 3, 6, 9):
                    for name, r in rows.items():
                        dec = "/".join(map(str, r["decoys"])) if r["decoys"] != "random" else "random"
                        print(f"  {B:6d}  {name:14s} {dec:>22s} {r['detected']:9.0%} {r['prevented']:10.0%} {r['hurt_per_1000']:10.1f} {r['payoff']:8.2f}")
        prof["sensitivity"] = sensitivity(hon, th)
        print("\nsensitivity, 1 attack per 1,000 honest requests: expected loss with "
              + " and ".join(map(str, SENSITIVITY_BUDGETS)) + " decoys (game / same number per type / random / all on passwords)")
        for row in prof["sensitivity"]:
            cells = []
            for B in SENSITIVITY_BUDGETS:
                r = row[str(B)]
                cells.append(" / ".join(f"{-r[p]['payoff']:5.2f}" for p in ("game", "same-per-type", "random", "crown-jewels"))
                             + f"  (game plants {'/'.join(map(str, r['game']['decoys']))})")
            print(f"  {row['change']:54s} " + "   ".join(cells))
        prof["honest_share_sweep"] = honest_share_sweep(hon, th)
        print("\nthe game's placement as honest requests touch each type more often (1 attack per 1,000 requests, 9 decoys):")
        for row in prof["honest_share_sweep"]:
            g = row["game"]
            print(f"  alarm {row['rule']:8s} share {row['share']:6.1%}: cost of protecting each type "
                  + "/".join(f"{x:.2f}" for x in row["costs"]) + f"; game plants {'/'.join(map(str, g['decoys']))}, loss {-g['payoff']:.2f}"
                  f" (same number in every type: {-row['same-per-type']['payoff']:.2f})")
        prof["ablations"] = ablations(hon, th)
        names = ["game", *ABLATIONS, "same-per-type", "value-proportional", "crown-jewels", "random"]
        print(f"\nablations and baselines (expected loss; decoys per type in brackets); decoy-aware thieves see through "
              f"{th['evade_high']:.0%} of high-realism and {th['evade_low']:.0%} of low-realism decoys")
        print(f"  {'realism':7s} {'requests/attack':>15s} {'decoys':>6s}  " + "  ".join(f"{n[:24]:>24s}" for n in names))
        for row in prof["ablations"]:
            cells = []
            for n in names:
                r = row[n]
                dec = "/".join(map(str, r["decoys"])) if r["decoys"] != "random" else "random"
                cells.append(f"{-r['payoff']:6.2f} [{dec:>6s}]".rjust(24))
            print(f"  {row['realism']:7s} {row['requests_per_attack']:15,d} {row['budget']:6d}  " + "  ".join(cells))
        report["profiles"][profile] = prof
    path = os.path.join(ROOT, "results", "placement_comparison.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    print(f"\nsaved {path}")


if __name__ == "__main__":
    main()
