"""Game-theoretic decoy placement across several types of file, as the experiments measured it.

A Stackelberg security game. The defender commits to a decoy share q_t for each type of file t
(passwords, customer records, bank details). Thieves know the policy but not which files are fake.
See MODEL.md, Part B, for the write-up. What the experiments changed from the simple model:

  1. Protecting a type has a FIXED cost K_t, paid as soon as it has any decoys (honest work runs into
     them or is confused by them about as often with 1 decoy as with 4), plus a small cost h_t per
     unit of decoy share. Both are penalties in the defender's payoff.
  2. Thieves come in kinds:
       pick-one        sends a single file; it is a decoy with chance (1 - evade) * q_t
       grab-everything sends every matching file; certain to be detected once the type has any
                       decoy, but the real secret leaves too (detected, not prevented)
     Every thief may also choose not to attack (worth 0 to both sides).
  3. Thieves go where the decoys are not, so all types are decided together.

Solved exactly: for each set of protected types (2^n sets) and each combination of the thieves'
choices, one linear program (the multiple-LP method of Conitzer & Sandholm 2006, with a Bayesian mix
of thief kinds as in Paruchuri et al. 2008). Ties go to the defender (strong Stackelberg equilibrium).

Run this file to check the claims in MODEL.md against brute force and the one-type formulas.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product

import numpy as np
from scipy.optimize import linprog

NO_ATTACK = None


@dataclass(frozen=True)
class AttackerType:
    name: str
    prob: float
    V: tuple[float, ...]        # gain per type from a real secret
    C: tuple[float, ...]        # cost per type when caught
    evade: float = 0.0          # share of decoys this kind recognizes and avoids (pick-one only)
    grab_all: bool = False      # sends every matching file instead of one


@dataclass(frozen=True)
class Solution:
    q: tuple[float, ...]                       # decoy share per type (0 = not protected)
    defender_payoff: float
    targets: dict[str, int | None]             # thief kind -> type it attacks (None = does not attack)
    cost: float                                # what the protection costs honest work


def _protected(q) -> tuple[bool, ...]:
    return tuple(x > 1e-12 for x in q)


def attacker_gain(q, t, a: AttackerType) -> float:
    if t is NO_ATTACK:
        return 0.0
    if a.grab_all:
        return a.V[t] - (a.C[t] if q[t] > 1e-12 else 0.0)
    c = (1 - a.evade) * q[t]
    return (1 - c) * a.V[t] - c * a.C[t]


def defender_outcome(q, t, a: AttackerType, L, G) -> float:
    if t is NO_ATTACK:
        return 0.0
    if a.grab_all:   # the secret leaves either way; a decoy in the type adds the value of detection
        return -L[t] + (G[t] if q[t] > 1e-12 else 0.0)
    c = (1 - a.evade) * q[t]
    return c * G[t] - (1 - c) * L[t]


def protection_cost(q, K, h) -> float:
    return float(sum(K[t] for t, on in enumerate(_protected(q)) if on) + np.dot(h, q))


def evaluate(q, types: list[AttackerType], L, G, K, h) -> Solution:
    """Defender payoff of any placement when each thief best-responds (ties broken for the defender)."""
    q = tuple(float(x) for x in q)
    n = len(q)
    total, targets = 0.0, {}
    for a in types:
        options = [*range(n), NO_ATTACK]
        best = max(attacker_gain(q, t, a) for t in options)
        t = max((t for t in options if attacker_gain(q, t, a) >= best - 1e-9),
                key=lambda t: defender_outcome(q, t, a, L, G))
        targets[a.name] = t
        total += a.prob * defender_outcome(q, t, a, L, G)
    cost = protection_cost(q, K, h)
    return Solution(q, float(total - cost), targets, cost)


def solve(types: list[AttackerType], L, G, K, h, q_min: float = 0.05, q_max: float = 0.8) -> Solution:
    """Best decoy shares. L, G, K, h are per-type sequences. A protected type gets a share between
    q_min (about one decoy) and q_max; an unprotected type gets none and costs nothing."""
    n = len(L)
    L, G, K, h = (np.asarray(x, float) for x in (L, G, K, h))
    best = None
    for protected in product((False, True), repeat=n):
        idx = [t for t in range(n) if protected[t]]           # LP variables: shares of protected types
        col = {t: j for j, t in enumerate(idx)}
        fixed = float(K[list(idx)].sum()) if idx else 0.0
        for combo in product([*range(n), NO_ATTACK], repeat=len(types)):
            obj = np.zeros(len(idx))                           # minimize -(payoff); constants kept apart
            const = -fixed
            A, b, ok = [], [], True
            for a, t in zip(types, combo):
                # defender's outcome against this kind
                if t is not NO_ATTACK:
                    if a.grab_all:
                        const += a.prob * (-L[t] + (G[t] if protected[t] else 0.0))
                    else:
                        const += a.prob * (-L[t])
                        if protected[t]:
                            obj[col[t]] -= a.prob * (1 - a.evade) * (G[t] + L[t])
                # this kind must (weakly) prefer t to every alternative s
                for s in [*range(n), NO_ATTACK]:
                    if s == t:
                        continue
                    row, rhs = np.zeros(len(idx)), 0.0          # gain(s) - gain(t) <= 0, written as row.q <= rhs
                    for target, sign in ((s, 1.0), (t, -1.0)):
                        if target is NO_ATTACK:
                            continue
                        if a.grab_all:
                            rhs -= sign * (a.V[target] - (a.C[target] if protected[target] else 0.0))
                        else:
                            rhs -= sign * a.V[target]
                            if protected[target]:
                                row[col[target]] -= sign * (1 - a.evade) * (a.V[target] + a.C[target])
                    if not idx:
                        if rhs < -1e-12:
                            ok = False
                        continue
                    A.append(row)
                    b.append(rhs)
            if not ok:
                continue
            obj = obj + h[idx] if idx else obj                  # per-share cost
            if idx:
                res = linprog(obj, A_ub=np.array(A) if A else None, b_ub=np.array(b) if b else None,
                              bounds=[(q_min, q_max)] * len(idx), method="highs")
                if not res.success:
                    continue
                q = np.zeros(n)
                q[idx] = res.x
            else:
                q = np.zeros(n)
            payoff = sum(a.prob * defender_outcome(q, t, a, L, G) for a, t in zip(types, combo)) - protection_cost(q, K, h)
            if best is None or payoff > best[0] + 1e-9:
                best = (payoff, q, combo)
    payoff, q, combo = best
    return Solution(tuple(float(x) for x in q), float(payoff),
                    {a.name: t for a, t in zip(types, combo)}, protection_cost(q, K, h))


def shares_to_counts(q, n_real) -> list[int]:
    """Decoys to plant so that decoys make up a share q of each type: k = q * n / (1 - q), rounded."""
    return [int(round(qi * n / (1 - qi))) if qi < 1 else 0 for qi, n in zip(q, n_real)]


# ---------------------------------------------------------------------------------------------- checks

def _grid_best(types, L, G, K, h, step=0.05, q_min=0.05, q_max=0.8):
    levels = [0.0] + list(np.arange(q_min, q_max + 1e-9, step))
    return max((evaluate(q, types, L, G, K, h) for q in product(levels, repeat=len(L))), key=lambda s: s.defender_payoff)


if __name__ == "__main__":
    import os
    import random
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from simple_model import best_q_strategic, defender_payoff, q_star

    # Check 1: one type, one naive pick-one thief, no fixed cost -> the simple model's Result 1.
    V, C, Lx, Gx = 10.0, 40.0, 100.0, 10.0
    for h in (1.0, 50.0, 1000.0):     # cheap, moderate and prohibitive per-share cost
        sol = solve([AttackerType("naive", 1.0, (V,), (C,))], [Lx], [Gx], [0.0], [h], q_min=1e-6)
        expect = best_q_strategic(V, C, Lx, Gx, 1.0, h)
        assert abs(sol.q[0] - expect) < 1e-6, (h, sol.q, expect)
        assert abs(sol.defender_payoff - defender_payoff(expect, V, C, Lx, Gx, 1.0, h)) < 1e-6
    print(f"check 1 passed: one type, naive thief -> q* = {q_star(V, C):.2f} or nothing, as in Result 1")

    # Check 2: a fixed cost above what protection saves -> do not protect (Result 3).
    thief = [AttackerType("naive", 1.0, (V,), (C,))]
    saved = Lx                                    # deterring the thief saves the whole leak
    assert solve(thief, [Lx], [Gx], [saved * 0.9], [0.0]).q[0] > 0
    assert solve(thief, [Lx], [Gx], [saved * 1.1], [0.0]).q[0] == 0
    print("check 2 passed: protect a type only when its fixed cost is below what protection saves")

    # Check 3: grab-everything thief: one decoy detects it; it is deterred only when C > V (Result 4).
    for C_ in (5.0, 40.0):
        g = [AttackerType("grab", 1.0, (V,), (C_,), grab_all=True)]
        sol = solve(g, [Lx], [Gx], [1.0], [1.0])
        deterred = sol.targets["grab"] is NO_ATTACK
        assert sol.q[0] <= 0.05 + 1e-9 and (deterred == (C_ > V)), (C_, sol)
    print("check 3 passed: against a grab-everything thief one decoy is enough; it deters only if C > V")

    # Check 4: random games, 3 types, mixed thieves: the solver is never beaten by a grid search.
    rng = random.Random(0)
    for trial in range(40):
        L_ = [rng.uniform(2, 12) for _ in range(3)]
        G_ = [rng.uniform(0, 4) for _ in range(3)]
        K_ = [rng.uniform(0, 3) for _ in range(3)]
        h_ = [rng.uniform(0, 3) for _ in range(3)]
        mk = lambda name, p, **kw: AttackerType(name, p, tuple(rng.uniform(1, 12) for _ in range(3)),
                                                 tuple(rng.uniform(1, 30) for _ in range(3)), **kw)
        ts = [mk("grab", 0.5, grab_all=True), mk("naive", 0.2), mk("aware", 0.3, evade=rng.uniform(0, 0.6))]
        sol = solve(ts, L_, G_, K_, h_)
        grid = _grid_best(ts, L_, G_, K_, h_)
        assert sol.defender_payoff >= grid.defender_payoff - 1e-6, (trial, sol, grid)
        again = evaluate(sol.q, ts, L_, G_, K_, h_)
        assert abs(again.defender_payoff - sol.defender_payoff) < 1e-6, (trial, sol, again)
    print("check 4 passed: 40 random games, the solver matches or beats every point of a grid search")

    # Demo with illustrative numbers (see MODEL.md, Part B, for where each one comes from).
    types_ = ["passwords", "customer records", "bank details"]
    L_, G_ = [10, 6, 8], [2, 2, 2]
    K_ = [1.5, 0.8, 0.3]      # honest staff ask for password files most often without naming them
    h_ = [0.5, 0.5, 0.5]      # small extra cost per unit of decoy share
    V_, C_ = (10, 6, 8), (20, 20, 20)
    mix = [AttackerType("grab-everything", 0.5, V_, C_, grab_all=True),
           AttackerType("naive pick-one", 0.2, V_, C_),
           AttackerType("decoy-aware pick-one", 0.3, V_, C_, evade=0.2)]
    sol = solve(mix, L_, G_, K_, h_)
    show = lambda q: ", ".join(f"{t} {x:.2f}" for t, x in zip(types_, q))
    print("\ndemo (illustrative numbers):")
    print(f"  game-optimal shares: {show(sol.q)}  payoff {sol.defender_payoff:.2f}  cost {sol.cost:.2f}")
    print("  thieves:", {k: (types_[v] if v is not None else "do not attack") for k, v in sol.targets.items()})
    for label, q in [("no decoys", [0, 0, 0]), ("same share everywhere (0.5)", [0.5, 0.5, 0.5]),
                     ("only the most valuable type (0.5)", [0.5, 0, 0])]:
        print(f"  {label:34s} payoff {evaluate(q, mix, L_, G_, K_, h_).defender_payoff:6.2f}")
    print("  decoys to plant with 2 real files per type:", dict(zip(types_, shares_to_counts(sol.q, [2, 2, 2]))))
    print("\nchecks passed")
