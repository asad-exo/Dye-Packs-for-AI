# The decoy game

This is the model behind the project, written so it can be explained at a whiteboard. Code that checks every claim: `simple_model.py` and `placement_solver.py`.

## 1. One kind of asset

**Setting.** The agent's drive holds password files. A share **q** of them are decoys that look like the real ones. An attacker's hidden note makes the hijacked agent grab one file.

| Symbol | Meaning |
|---|---|
| q | share of look-alike files that are decoys (the defender chooses this) |
| V | attacker's gain from a real file |
| C | attacker's cost when caught (address blocked, trick exposed) |
| L | defender's loss from a leak |
| G | defender's gain from a catch |
| F | defender's cost of one false alarm |
| h | how many false alarms the honest agent causes per unit of q |

**Order of play (Stackelberg).** The defender commits to q first. The attacker knows q, but not which files are fake, and then decides whether to attack.

**Attacker.** The grabbed file is real with probability 1 − q and a decoy with probability q:

    attacker's gain = (1 − q)·V − q·C

The attacker attacks only if this is positive. It is zero at

    q* = V / (V + C)

Below q*, attacking pays. At or above q*, it does not. (At exactly q* the attacker is indifferent; the standard convention, the *strong Stackelberg equilibrium*, breaks the tie in the defender's favor.)

**Defender.** Decoys cost false alarms: the honest agent trips them at a rate h·q, each costing F.

    if the attacker attacks:   payoff = q·G − (1 − q)·L − F·h·q
    if the attacker is deterred: payoff = − F·h·q

**Result 1 (strategic attacker).** The best decoy share is either q* or 0:

- plant exactly **q\*** if the false alarms that costs are cheaper than a leak: F·h·q* < L
- otherwise plant **nothing**

Why: more decoys than q* only add false alarms, since the attacker is already deterred. Fewer than q* does not deter, so the attacker still attacks. So the defender never wants more than q*, and a share strictly between 0 and q* is always beaten by either 0 or q*. (This assumes being attacked at q* is worse for the defender than not being attacked, i.e. (1 − q*)·L > q*·G, which holds whenever leaks are costly.)

*Example.* V = 10, C = 40 gives q* = 0.2. With L = 100, F = 50, h = 1, the false alarms at q* cost 10, far below the leak loss of 100, so plant one decoy for every four real files. If the honest agent were clumsy (h = 12), the cost would be 120 > 100 and decoys would not be worth it.

**Result 2 (some attackers attack no matter what).** Suppose a share p of attackers are strategic and the rest always attack (they never learned about decoys, or do not care). Beyond q*, each extra decoy catches more of the always-attackers but adds false alarms. So:

- if (1 − p)·(L + G) < F·h, stop at **q\***
- if (1 − p)·(L + G) > F·h, keep adding decoys up to whatever cap is practical

**What this means for the "sweet spot".** With costs that grow in a straight line, the best q sits at one of three points: 0, q*, or the cap. q* is the interior sweet spot. A smoother peak appears when false alarms grow faster than linearly in q (an agent surrounded by decoys trips over them disproportionately). Whether that happens is an empirical question the experiments will answer by measuring h at different decoy counts.

## 2. Several kinds of assets

Now there are asset classes t = credentials, customer records, bank details. Each has its own values V_t, C_t, L_t, G_t and its own honest-agent rate h_t. The defender picks a decoy share q_t for each class, and cannot exceed a false-alarm budget B:

    sum over t of  h_t · q_t  ≤  B

The attacker sees the policy and attacks the class where (1 − q_t)·V_t − q_t·C_t is largest.

This is a Stackelberg security game where decoy share plays the role of "coverage". In the standard notation, the covered and uncovered payoffs are U_d^c = G_t, U_d^u = −L_t, U_a^c = −C_t, U_a^u = V_t. What is new is the false-alarm budget, which replaces the usual limit on the number of guards: decoys are cheap to make, and what limits them is the honest agent tripping over them.

**How it is solved.** For each class the attacker might choose, solve one linear program: maximize the defender's payoff subject to (a) the attacker really does prefer that class and (b) the false-alarm budget. Keep the best of these. This is the multiple-LP method of Conitzer and Sandholm (2006).

**Intuition for the answer.** The solver puts more decoys where the attacker gains most and where the honest agent rarely goes (low h_t), until the attacker is indifferent between classes. Spreading decoys evenly wastes budget on classes the honest agent uses a lot.

## 3. Several kinds of attackers

Attackers differ. A **naive** attacker does not think about decoys. A **decoy-aware** attacker recognizes and avoids a share of them, so it faces less coverage than the defender planted. The defender does not know which type it faces, only the mix (say 70% naive, 30% aware), and maximizes its expected payoff over that mix. This is a Bayesian Stackelberg game (Paruchuri et al., 2008). At this size it is solved by one linear program per combination of the types' choices.

In the code, a type's `evade` is the share of decoys it avoids; the coverage it faces is (1 − evade)·q_t. That is a linear approximation, reasonable when q_t is not large. The share avoided depends on decoy realism, and will be measured in the experiments.

## 4. From shares to decoys

If a class has n real items, a decoy share q needs k = q·n / (1 − q) decoys. With only two real items per class this rounding is coarse (0, 1 or 2 decoys), so the experiments will either use more real items per class or randomize the rounding.

## 5. What is assumed, and what gets measured

| Quantity | Status |
|---|---|
| V, C, L, G, F | Chosen for illustration; results will be reported across a range of values |
| h_t (honest-agent false alarms) | **Measured** with real AI agents on normal tasks |
| catch rates per attacker type and realism | **Measured** with the scripted attackers (and later real hijacks) |
| attacker mix | Assumed; varied in a sensitivity check |
