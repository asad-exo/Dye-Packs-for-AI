"""Feasibility check 1: the simple model and a small multi-asset Stackelberg solver (no API needed)."""
import numpy as np
from scipy.optimize import linprog

print("=== 1. Simple model: smallest decoy share that deters an attacker ===")
for V, C in [(10, 40), (10, 10), (10, 90), (50, 50)]:
    q = V / (V + C)
    gain_at = lambda qq: (1 - qq) * V - qq * C
    print(f"V={V:3d} C={C:3d} -> q* = {q:.2f}   check: attacker gain at q*={gain_at(q):+.2f}, "
          f"just below={gain_at(q-0.01):+.2f}, just above={gain_at(q+0.01):+.2f}")

print("\n=== 2. Realism trade-off (toy numbers) ===")
# Decoys that look fake (prob 1-r) are recognised and skipped; attacker picks among items that look real.
# Honest agent touches a decoy by mistake with prob proportional to density and realism.
V, C, LEAK, ALARM_COST, EPS = 10, 40, 100, 30, 0.10
best = None
for r in [0.3, 0.6, 0.9, 1.0]:
    rows = []
    for q in np.linspace(0, 0.6, 61):
        share_fake_among_real_looking = q * r / (q * r + (1 - q)) if q > 0 else 0.0
        attacker_gain = (1 - share_fake_among_real_looking) * V - share_fake_among_real_looking * C
        attacks = attacker_gain > 0
        p_leak = (1 - share_fake_among_real_looking) if attacks else 0.0
        false_alarm = min(1.0, EPS * q * r * 4)  # honest mistakes rise with density and realism
        defender_loss = LEAK * p_leak + ALARM_COST * false_alarm
        rows.append((defender_loss, q))
    loss, q_best = min(rows)
    print(f"realism r={r:.1f}: best decoy share q={q_best:.2f}, defender loss={loss:.1f}")
    if best is None or loss < best[0]:
        best = (loss, q_best, r)
print(f"overall best: share={best[1]:.2f} at realism={best[2]:.1f} (an interior choice, not 'max everything')")

print("\n=== 3. Multi-asset Stackelberg game, multiple-LP method (Conitzer & Sandholm) ===")
targets = ["tools", "files", "credentials", "contacts"]
Va = np.array([6.0, 8.0, 10.0, 3.0])      # attacker's gain from a real asset
Ca = np.array([20.0, 20.0, 20.0, 20.0])  # attacker's cost when caught
Ld = np.array([6.0, 8.0, 10.0, 3.0])      # defender's loss from a leak
Gd = np.array([2.0, 2.0, 2.0, 2.0])       # defender's gain from catching an attack
h = np.array([0.30, 0.20, 0.05, 0.10])    # honest agent's mistake rate per unit of decoy coverage
BUDGET = 0.12                              # allowed false-alarm rate
n = len(targets)


def att_u(c, t):
    return (1 - c[t]) * Va[t] - c[t] * Ca[t]


def def_u(c, t):
    return -(1 - c[t]) * Ld[t] + c[t] * Gd[t]


best = None
for t in range(n):
    # maximise defender utility at t  <=> minimise -( -(1-c_t)L + c_t G ) = -(L+G) c_t + L
    obj = np.zeros(n)
    obj[t] = -(Ld[t] + Gd[t])
    A, b = [], []
    for s in range(n):  # attacker prefers t: att_u(s) <= att_u(t)
        if s == t:
            continue
        row = np.zeros(n)
        row[s] = -(Va[s] + Ca[s])
        row[t] = (Va[t] + Ca[t])
        A.append(row)
        b.append(Va[t] - Va[s])
    A.append(h.copy())
    b.append(BUDGET)
    res = linprog(obj, A_ub=np.array(A), b_ub=np.array(b), bounds=[(0, 1)] * n, method="highs")
    if res.success:
        c = res.x
        du = def_u(c, t)
        if best is None or du > best[0] + 1e-9:
            best = (du, t, c)
du, t_star, c_opt = best
print("game-optimal decoy coverage:", {k: round(v, 2) for k, v in zip(targets, c_opt)},
      f"| false-alarm rate {h @ c_opt:.3f} (limit {BUDGET})")
print(f"attacker's best response: {targets[t_star]}; defender payoff {du:.2f}")


def evaluate(c, label):
    au = [att_u(c, s) for s in range(n)]
    tb = max(range(n), key=lambda s: (round(au[s], 9), def_u(c, s)))  # ties broken in defender's favour
    print(f"{label:28s} coverage={np.round(c, 2)} false-alarm={h @ c:.3f} attacker->{targets[tb]:11s} "
          f"defender payoff={def_u(c, tb):.2f}")


uniform = np.full(n, BUDGET / h.sum())
evaluate(uniform, "uniform (same everywhere)")
most_valuable = np.zeros(n); most_valuable[2] = min(1.0, BUDGET / h[2])
evaluate(most_valuable, "guard most valuable only")
evaluate(c_opt, "game-optimal (LP)")
