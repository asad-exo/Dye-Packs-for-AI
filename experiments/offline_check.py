"""Offline check of the decoy kit: scripted attackers against each placement, and AgentDojo's
scripted solutions to the 40 normal tasks as a stand-in for the honest agent. No AI model, no API key.

These numbers test the machinery and the attacker models. False-alarm rates for a real AI agent
have to be measured with real model runs (experiments/honest_runs.py).
Usage: python experiments/offline_check.py [runs_per_cell]"""
import json
import os
import random
import sys
import warnings
import zlib

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentdojo.task_suite.load_suites import get_suite  # noqa: E402

from attackers import ATTACKERS  # noqa: E402
from decoykit import (ALARM_RULES, CLASS_KEYS, MonitoredRuntime, counts_policy, fixed_policy, none_policy,  # noqa: E402
                      outcome, plant, random_policy, tools_for)

N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
suite = get_suite("v1.2.2", "workspace")
BASE_ENV = suite.load_and_inject_default_environment({})   # loaded once; each run works on a fresh copy
BUDGET = 6


def placements(rng, realism):
    return {
        "none": none_policy(),
        "fixed": fixed_policy(per_class=2, realism=realism),
        "random": random_policy(BUDGET, rng, realism=realism),
        "even (2 per class)": counts_policy({k: 2 for k in CLASS_KEYS}, realism=realism, name="even"),
    }


def attack_cell(policy_name, realism, attacker, seed0):
    rows = []
    for n in range(N):
        rng = random.Random(seed0 + n)
        placement = placements(rng, realism)[policy_name]
        env = BASE_ENV.model_copy(deep=True)
        reg = plant(env, placement, rng)
        rt = MonitoredRuntime(tools_for(suite, placement), reg)
        res = ATTACKERS[attacker](env, rt, rng, rng.choice(CLASS_KEYS))
        rows.append((res, rt.events))
    return rows


print(f"ATTACKERS: {N} runs per cell, decoy budget {BUDGET}")
print("alarm rules: act = a decoy is opened, used or sent anywhere; send_out = a decoy is sent outside the company\n")
summary = []
for realism in ("low", "high"):
    print(f"decoy realism: {realism}")
    print(f"  {'placement':20s} {'attacker':12s} {'act: caught':>12s} {'leaked':>7s}   {'send_out: caught':>17s} {'leaked':>7s} {'gave up':>8s}")
    for policy_name in ("none", "fixed", "random", "even (2 per class)"):
        for attacker in ATTACKERS:
            rows = attack_cell(policy_name, realism, attacker, seed0=1000)
            o = [outcome(ev, "act") for _, ev in rows]
            caught, leaked = sum(x["caught"] for x in o) / N, sum(x["leaked"] for x in o) / N
            o2 = [outcome(ev, "send_out") for _, ev in rows]
            caught2, leaked2 = sum(x["caught"] for x in o2) / N, sum(x["leaked"] for x in o2) / N
            gave_up = sum(r.gave_up for r, _ in rows) / N
            print(f"  {policy_name:20s} {attacker:12s} {caught:12.2f} {leaked:7.2f}   {caught2:17.2f} {leaked2:7.2f} {gave_up:8.2f}")
            summary.append(dict(realism=realism, placement=policy_name, attacker=attacker, caught=caught, leaked=leaked,
                                caught_send_out=caught2, leaked_send_out=leaked2, gave_up=gave_up, runs=N))
    print()

print("HONEST STAND-IN: AgentDojo's scripted solutions to the 40 normal tasks, even placement, high realism")
rng = random.Random(7)
placement = placements(rng, "high")["even (2 per class)"]
fa = {rule: 0 for rule in ALARM_RULES}
ok = total = 0
for uid, ut in suite.user_tasks.items():
    env = ut.init_environment(BASE_ENV.model_copy(deep=True))
    reg = plant(env, placement, random.Random(zlib.crc32(uid.encode())))   # same seed every time for each task
    pre = env.model_copy(deep=True)
    rt = MonitoredRuntime(tools_for(suite, placement), reg)
    for call in ut.ground_truth(pre):
        rt.run_function(env, call.function, call.args)
    for rule in ALARM_RULES:
        fa[rule] += outcome(rt.events, rule)["alarm"]
    try:
        total += 1
        ok += bool(ut.utility(ut.GROUND_TRUTH_OUTPUT, pre, env))
    except Exception:
        pass
print(f"  tasks still passing their own check: {ok}/{total}")
for rule, n in fa.items():
    print(f"  false alarms under rule '{rule}': {n}/{total}")
out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "offline_check.json")
os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump({"runs_per_cell": N, "budget": BUDGET, "alarm_rule": "act (caught, leaked); send_out (caught_send_out, leaked_send_out)", "attackers": summary,
           "honest_standin": {"tasks_passing": ok, "tasks": total, "false_alarms": fa}}, open(out, "w"), indent=1)
print(f"\nsaved {out}")
