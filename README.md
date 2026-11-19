# Dye Packs for AI

Game-theoretic decoys that catch hijacked AI agents.

Course project for ECE-GY 6263 Game Theory (NYU Tandon, Fall 2026) by Asad Shahab Shafqat.

**The idea:** plant decoys (fake files, fake tools, fake credentials) in an AI agent's workspace. The company's own agent never needs them, so an agent that opens, uses or leaks one has probably been hijacked by hidden instructions. A Stackelberg security game decides how many decoys to plant, how realistic to make them, and where.

## Status

Building. The decoy kit, the scripted attackers and the game model are written and checked offline. Next: measure how often real AI agents set off false alarms, then compare decoy placements. The model is explained in [model/MODEL.md](model/MODEL.md).

Pilot findings (October 2026) (106 agent runs in AgentDojo's workspace environment, Claude Haiku 5.5 and 4.5):

- 0 of 40 normal tasks raised an alarm when the alarm fires only if a decoy is opened, used or leaked. Counting any sighting of a decoy in a file listing would have flagged 9 of 40.
- 37 of 40 normal tasks completed with decoys present. The no-decoy baseline has not been run yet.
- Both models resisted all 48 built-in hidden-instruction attacks.
- Given the attacker's goal directly, an agent opened the fake passwords file in 2 runs, and the alarm fired both times.
- 3 runs that emailed the attacker without touching a decoy were not caught.

## Layout

| Path | Contents |
|---|---|
| `model/MODEL.md` | The game, written to be explained at a whiteboard: the deterrence threshold q* = V / (V + C), the false-alarm cost, several asset classes, and attacker types. |
| `model/simple_model.py` | The one-asset game in code; checks Results 1 and 2 numerically. |
| `model/placement_solver.py` | The multi-asset Stackelberg solver with a false-alarm budget and attacker types (one linear program per attacker choice). |
| `decoykit/` | The decoy kit: asset classes with real items and decoys at three realism levels, placement policies, and the alarm monitor. See [decoykit/README.md](decoykit/README.md). |
| `attackers/` | Four scripted hijacked agents: grab_all, pick_one, decoy_aware, informed. See [attackers/README.md](attackers/README.md). |
| `experiments/offline_check.py` | Scripted attackers against each placement, plus AgentDojo's scripted task solutions as a stand-in for the honest agent. No API key needed. |
| `experiments/honest_runs.py` | Real AI agents do the 40 normal tasks under 11 decoy settings, to measure false alarms and any cost to task success. Needs an API key; about $1.20 for one full pass on Claude Haiku 5.5. |
| `experiments/check_setup.py` | Free check that AgentDojo and the Anthropic library work together (the network is faked; no key, no cost). |
| `experiments/anthropic_compat.py` | Fixes AgentDojo's Anthropic adapter for current versions of the Anthropic library. |
| `experiments/pilot/` | The October feasibility pilot: `run_pilot.py` (real AI agents; needs a key), `scripted_decoy_test.py`, `summarize_pilot.py`. |
| `results/` | Raw results: `pilot/` from October, `offline_check.json` from the scripted attackers. |
| `model/simple_model_check.py` | Early sketch from the proposal stage, replaced by the two model files above. |
| `figures/`, `paper/` | Charts and the report; empty for now. |

## Setup

Requires Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

Run everything from the repository's top folder.

```bash
# No API key needed
python model/simple_model.py                 # checks Results 1 and 2
python model/placement_solver.py             # solver demo: game placement vs. even and top-only
python experiments/offline_check.py 200      # scripted attackers, 200 runs per setting (about 15 seconds)
python experiments/check_setup.py     # confirms the model setup works, for free
python experiments/pilot/summarize_pilot.py  # the pilot numbers above
```

To run real agents, set your Anthropic API key first. Never put the key in a file inside this repo.

```bash
export ANTHROPIC_API_KEY="sk-ant-..."     # Windows PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-..."

python experiments/honest_runs.py --plan     # what would run and what it would cost; spends nothing
python experiments/honest_runs.py --limit 5  # a 5-run smoke test (about 2 cents)
python experiments/honest_runs.py            # the full pass; stops by itself at $5, resumes if restarted
python experiments/honest_runs.py --summary  # false-alarm and task-success tables
```

Results are saved to `results/honest/<model>.jsonl`, one line per run.

The October pilot can still be re-run with `python experiments/pilot/run_pilot.py`. Its options, set as environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `MODEL` | `claude-haiku-5-5` | Model to run |
| `KINDS` | `normal,attacked,direct` | Which run types to include |
| `OUT` | `pilot_run.json` | Where to save results |
| `SYS` | AgentDojo's default | Replacement system prompt |

The full default run is 73 agent runs and cost about $0.20 on Claude Haiku 5.5 in October 2026.

## Notes

- All data in AgentDojo is synthetic. The "attacker" address and the decoy contents are made up.
- AgentDojo 0.1.35 does not work with current versions of the Anthropic library as shipped. `experiments/anthropic_compat.py` fixes the two problems found so far; every script that runs Claude imports it first.
- Figures explaining the project (how hijacking works, how decoys catch it, the game, the results) will be added to this README as the experiments finish.
