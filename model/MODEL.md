# The decoy game

This is the model behind the project, written so it can be explained at a whiteboard. Part A is the simple model from the proposal. Part B is the model after the experiments: what they measured, and how that changes the game. Code that checks every claim: `simple_model.py` (Part A) and `placement_solver.py` (Part B).

# Part A: the simple model

## 1. One kind of file

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

**What this means for the "sweet spot".** With costs that grow in a straight line, the best q sits at one of three points: 0, q*, or the cap. q* is the interior sweet spot.

# Part B: the model after the experiments

## 2. What the experiments showed

Three findings do not fit Part A. Each comes from runs with real AI agents (`results/honest/`, `results/hijack/`; numbers in the main README).

1. **The cost of decoys switches on; it does not grow with each decoy.** With 1, 2 or 4 decoys per type, honest agents ran into them about equally often: an honest search either goes near the password files or it does not. So protecting a type of file has a **fixed cost**, plus only a small extra per decoy. (The weakest agent, Qwen3, did get somewhat worse with more decoys: its right answers went from 100% to 83% to 78% at 1, 2 and 4 decoys per type. So the per-decoy cost is small, not zero.)
2. **Decoys also cost honest work through confusion, not only through alarms.** Decoys hold different values from the real file. When a request did not name the file, the agent gave the right answer in 86-96% of runs instead of 100%. With the alarm that fires only when a decoy is sent outside the company, honest agents caused no false alarms at all (0 of 1,958 runs), so most of the cost is confusion.
3. **Hijacked agents often take everything at once.** A naive hijacked agent (one whose instructions do not mention decoys) usually emailed every matching file in one message (Claude: 20 of 20 times it sent anything; Qwen3: 133 of 162 runs). The decoys in that message set off the alarm, but the real secret left with them: **detected, not prevented.** A decoy-aware agent sent a single file. Against realistic decoys it still picked a decoy about half the time (a blind pick would hit one 50-67% of the time), so it saw through few of them.

## 3. The model, as measured

**Cost of protecting a type of file t.**

    cost = K_t  (once, if the type has any decoys)  +  h_t · q_t

K_t is the fixed cost (mostly confusion of honest work, plus any false alarms). It is large for a type that honest staff often look for without naming the file, such as passwords, and small for one they rarely need. h_t is the small extra cost per unit of decoy share. Both are subtracted from the defender's payoff, as in Part A.

**Kinds of thief.** Each thief knows the defender's policy, but not which files are fake.

| Kind | What it does | If the type it targets has decoys | If it has none |
|---|---|---|---|
| **Pick-one** | sends a single file | the file is a decoy with chance c = (1 − e)·q: thief gets (1 − c)·V − c·C, defender gets c·G − (1 − c)·L | thief V, defender −L |
| **Grab-everything** | sends every matching file | always detected, but the real secret leaves too: thief V − C, defender −L + G | thief V, defender −L |

e is the share of decoys the thief can recognize: 0 for a naive thief, more for a decoy-aware one. Every thief can also **choose not to attack**, which is worth 0 to both sides. G is now the value of detection itself: blocking the agent and changing the stolen passwords.

**Result 3 (protect or not).** With a fixed cost, the real decision is *which types of file to protect*. For a protected type, the best share is still the smallest one that does the job: the type's q\* (raised to make up for what decoy-aware thieves see through), or the cap when many thieves attack regardless. Protect a type only if what protection saves, in attacks deterred or caught, is worth more than its fixed cost K_t.

**Result 4 (grab-everything thieves).** One decoy in a type is enough to detect every grab-everything thief that targets it; more decoys add nothing against them. Detection does not stop the leak. It deters such a thief only if being caught costs it more than the secret is worth (C > V). Otherwise decoys turn a silent theft into a detected one.

**Result 5 (thieves go where the decoys are not).** Protecting one type pushes thieves to the types left open. So all types must be decided together, and protecting only some types can be pointless.

*Examples* (illustrative numbers, from `placement_solver.py`; three types, half the thieves grab everything, the rest pick one file, some of them decoy-aware):

- **Thieves fear getting caught (C greater than V):** protect every type with just enough decoys that attacking does not pay. Every thief stays away.
- **Protecting passwords is very costly** (honest staff search for them constantly): protect *nothing*. Thieves would simply go for the passwords, so protecting the other types would be wasted (Result 5).
- **Getting caught does not scare thieves (C less than V):** decoys cannot deter, so the best use is to *steer*. Protect the passwords and bank details, and leave customer records open, so thieves take the least damaging target.

## 4. Several types of file and several kinds of thief: the solver

This is a Stackelberg security game in which decoy share plays the role of "coverage". In the standard notation, the covered and uncovered payoffs for a pick-one thief are U_d^c = G_t, U_d^u = −L_t, U_a^c = −C_t, U_a^u = V_t. What is new:

- the cost of coverage is measured on honest agents, and it is mostly fixed, not proportional to coverage
- some thieves grab everything, so coverage detects them without protecting the asset
- the defender does not know which kind of thief it faces, only the mix (a Bayesian Stackelberg game; Paruchuri et al., 2008)

**How it is solved.** For each set of protected types (8 sets for 3 types) and each combination of the thieves' choices (including not attacking), solve one linear program: maximize the defender's expected payoff, minus the protection costs, subject to every kind of thief really preferring its choice. Keep the best. This is the multiple-LP method of Conitzer and Sandholm (2006), run once per protected set. It is exact, and at this size it takes seconds. The code checks it against the one-type formulas of Part A and against a brute-force grid search on 40 random games.

`experiments/placement_comparison.py` uses the same payoffs to compare the game's placements with simpler ones (the same number of decoys in every type, a random split, a split by value, all on passwords), with the numbers the runs measured. It also solves two cut-down versions of the game, one with no decoy-aware thieves and one with no cost to honest work, and scores their placements with the full model, to show what each part adds. The results are in the main README.

## 5. From shares to decoys

If a type has n real files, a decoy share q needs k = q·n / (1 − q) decoys. With only two real files per type this rounding is coarse (0, 1 or 2 decoys), so the experiments either use more real files per type or randomize the rounding.

## 6. What is assumed, and what is measured

| Quantity | Status |
|---|---|
| V, C, L, G | Chosen for illustration; the placement comparison changes them one at a time |
| K_t, the fixed cost of protecting a type | **Measured** per request: no cost when the request names the file; right answer 86-96% instead of 100% when it does not; false alarms per request under each alarm rule. How often honest work looks for each type is assumed and varied from 0.1% to 30% of requests (main README, "False alarms against the share of sensitive work") |
| h_t, the extra cost per decoy | **Measured** small (larger for the weakest agent) |
| Share of grab-everything thieves | **Measured** on hijacked agents: most naive hijacked agents sent everything at once |
| e, decoys a decoy-aware thief recognizes | **Measured**: Qwen3 picked a decoy 26% of the time against low-realism decoys (a blind pick: 50%), and 46-59% of the time against high-realism ones (a blind pick: 50-67%), so e is about 10% for high realism. Claude: none (it picked a decoy in 33 of 56 single-file sends, where a blind pick would hit about 31) |
| Mix of thief kinds | Assumed (70% naive, 30% decoy-aware); the placement comparison also tries 50% and 90% naive |

Two tests on fresh data (`experiments/validation.py`) checked the measured model: for each of Claude and Qwen3, the placement the game recommends was run for the first time, with the prediction written down beforehand. Both predictions fell inside the 95% intervals of what was measured; the numbers are in the main README.
