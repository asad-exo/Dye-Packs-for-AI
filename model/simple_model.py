"""The simple (one asset class) decoy game with an explicit false-alarm cost.

Symbols
  q   share of look-alike items that are decoys (the defender's choice, 0 <= q < 1)
  V   attacker's gain from a real item          C   attacker's cost when caught
  L   defender's loss from a leak               G   defender's gain from a catch
  F   defender's cost per false alarm           h   false alarms per unit of q from the honest agent
See MODEL.md for the write-up. Run this file to check the claims numerically.
"""
from __future__ import annotations


def q_star(V: float, C: float) -> float:
    """Smallest decoy share at which attacking stops paying: the attacker's indifference point."""
    return V / (V + C)


def attacker_gain(q: float, V: float, C: float) -> float:
    return (1 - q) * V - q * C


def attacks(q: float, V: float, C: float) -> bool:
    """A strategic attacker attacks only if the gain is strictly positive (ties go to the defender)."""
    return attacker_gain(q, V, C) > 1e-12


def false_alarm_cost(q: float, F: float, h: float) -> float:
    return F * h * q


def defender_payoff(q: float, V: float, C: float, L: float, G: float, F: float, h: float,
                    attacker_always_attacks: bool = False) -> float:
    cost = false_alarm_cost(q, F, h)
    if attacker_always_attacks or attacks(q, V, C):
        return q * G - (1 - q) * L - cost
    return -cost


def best_q_strategic(V, C, L, G, F, h) -> float:
    """Against a strategic attacker: plant exactly q* if its false-alarm cost is below the leak loss, else nothing."""
    qs = q_star(V, C)
    return qs if false_alarm_cost(qs, F, h) < L else 0.0


def defender_payoff_mixed(q, p_strategic, V, C, L, G, F, h) -> float:
    """A mix of attackers: a share p is strategic, the rest attack no matter what."""
    return (p_strategic * defender_payoff(q, V, C, L, G, F, h)
            + (1 - p_strategic) * defender_payoff(q, V, C, L, G, F, h, attacker_always_attacks=True))


if __name__ == "__main__":
    V, C, L, G = 10.0, 40.0, 100.0, 10.0
    qs = q_star(V, C)
    print(f"q* = V/(V+C) = {qs:.2f}; attacker gain just below / at / just above: "
          f"{attacker_gain(qs-.01, V, C):+.2f} / {attacker_gain(qs, V, C):+.2f} / {attacker_gain(qs+.01, V, C):+.2f}")
    grid = [i / 1000 for i in range(0, 991)]
    for F, h in [(50, 1.0), (50, 12.0)]:
        best = max(grid, key=lambda q: defender_payoff(q, V, C, L, G, F, h))
        print(f"F={F}, h={h}: grid optimum q={best:.3f}, formula says {best_q_strategic(V, C, L, G, F, h):.3f} "
              f"(false-alarm cost at q*: {false_alarm_cost(qs, F, h):.0f} vs leak loss L={L:.0f})")
        assert abs(best - best_q_strategic(V, C, L, G, F, h)) < 2e-3
    print("checks passed")
