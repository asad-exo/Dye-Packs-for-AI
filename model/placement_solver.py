"""Game-theoretic decoy placement across several asset classes.

A Stackelberg security game: the defender commits to a decoy share q_t for each asset class t, under
a false-alarm budget  sum_t h_t * q_t <= B.  The attacker sees the policy and attacks the class with
the best expected gain. Solved exactly with the multiple-LP method (Conitzer & Sandholm 2006): one
linear program per class the attacker might choose.

With several attacker types (Bayesian Stackelberg, as in Paruchuri et al. 2008) there is one linear
program per combination of choices, which is fine at this size. A type can also see through a share
of the decoys: `evade` is the fraction of decoys that type recognizes and avoids, so the coverage it
actually faces is (1 - evade) * q_t. That is a linear approximation, good when q_t is not large.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product

import numpy as np
from scipy.optimize import linprog


@dataclass(frozen=True)
class AttackerType:
    name: str
    prob: float
    V: tuple[float, ...]        # gain per class from a real item
    C: tuple[float, ...]        # cost per class when caught
    evade: float = 0.0          # share of decoys this type recognizes and avoids


@dataclass(frozen=True)
class Solution:
    q: tuple[float, ...]                 # decoy share per class
    defender_payoff: float
    targets: dict[str, int]              # attacker type -> class it attacks
    false_alarm_rate: float


def _att_u(q, t, a: AttackerType):
    c = (1 - a.evade) * q[t]
    return (1 - c) * a.V[t] - c * a.C[t]


def _def_u(q, t, a: AttackerType, L, G):
    c = (1 - a.evade) * q[t]
    return c * G[t] - (1 - c) * L[t]


def solve(types: list[AttackerType], L, G, h, budget: float, q_max: float = 0.8) -> Solution:
    """Optimal decoy shares. L, G, h are per-class sequences; budget is the allowed false-alarm rate."""
    n = len(L)
    L, G, h = (np.asarray(x, float) for x in (L, G, h))
    best = None
    for combo in product(range(n), repeat=len(types)):
        obj = np.zeros(n)            # minimize -(defender payoff); constants dropped
        A, b = [h.copy()], [budget]
        for a, t in zip(types, combo):
            k = 1 - a.evade
            obj[t] -= a.prob * k * (L[t] + G[t])
            for s in range(n):       # type a must weakly prefer t to s
                if s == t:
                    continue
                row = np.zeros(n)
                row[s] = -k * (a.V[s] + a.C[s])
                row[t] += k * (a.V[t] + a.C[t])
                A.append(row)
                b.append(a.V[t] - a.V[s])
        res = linprog(obj, A_ub=np.array(A), b_ub=np.array(b), bounds=[(0, q_max)] * n, method="highs")
        if not res.success:
            continue
        q = res.x
        payoff = sum(a.prob * _def_u(q, t, a, L, G) for a, t in zip(types, combo))
        if best is None or payoff > best[0] + 1e-9:
            best = (payoff, q, combo)
    if best is None:
        raise RuntimeError("no feasible placement")
    payoff, q, combo = best
    return Solution(tuple(float(x) for x in q), float(payoff), {a.name: t for a, t in zip(types, combo)}, float(h @ q))


def evaluate(q, types: list[AttackerType], L, G, h) -> Solution:
    """Defender payoff of any placement q when each type best-responds (ties broken for the defender)."""
    L, G, h = (np.asarray(x, float) for x in (L, G, h))
    q = np.asarray(q, float)
    total, targets = 0.0, {}
    for a in types:
        gains = [_att_u(q, t, a) for t in range(len(q))]
        top = max(gains)
        t = max((t for t in range(len(q)) if gains[t] >= top - 1e-9), key=lambda t: _def_u(q, t, a, L, G))
        targets[a.name] = t
        total += a.prob * _def_u(q, t, a, L, G)
    return Solution(tuple(float(x) for x in q), float(total), targets, float(h @ q))


def shares_to_counts(q, n_real) -> list[int]:
    """Decoys to plant so that decoys make up a share q of each class: k = q * n / (1 - q), rounded."""
    return [int(round(qi * n / (1 - qi))) if qi < 1 else 0 for qi, n in zip(q, n_real)]


if __name__ == "__main__":
    classes = ["credentials", "customer_data", "financial"]   # illustrative numbers only
    L, G, h, B = [10, 6, 8], [2, 2, 2], [0.05, 0.30, 0.15], 0.10
    naive = AttackerType("naive", 0.7, V=(10, 6, 8), C=(20, 20, 20))
    aware = AttackerType("decoy_aware", 0.3, V=(10, 6, 8), C=(20, 20, 20), evade=0.5)
    for label, types in [("one naive type", [AttackerType("naive", 1.0, naive.V, naive.C)]),
                         ("70% naive, 30% decoy-aware", [naive, aware])]:
        sol = solve(types, L, G, h, B)
        uniform = evaluate([B / sum(h)] * 3, types, L, G, h)
        top = [0.0, 0.0, 0.0]; top[0] = min(0.8, B / h[0])
        top_only = evaluate(top, types, L, G, h)
        print(f"\n{label}")
        print("  game-optimal shares:", dict(zip(classes, np.round(sol.q, 2))), f"payoff {sol.defender_payoff:.2f}",
              f"false-alarm rate {sol.false_alarm_rate:.3f}", "| attacks:", {k: classes[v] for k, v in sol.targets.items()})
        print(f"  same share everywhere: payoff {uniform.defender_payoff:.2f} | guard only the most valuable: payoff {top_only.defender_payoff:.2f}")
        print("  decoys to plant (2 real items per class):", dict(zip(classes, shares_to_counts(sol.q, [2, 2, 2]))))
        assert sol.defender_payoff >= max(uniform.defender_payoff, top_only.defender_payoff) - 1e-6
    print("\nchecks passed")
