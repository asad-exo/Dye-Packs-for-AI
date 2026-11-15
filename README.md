# Dye Packs for AI

Game-theoretic decoys that catch hijacked AI agents.

Course project for ECE-GY 6263 Game Theory (NYU Tandon, Fall 2026) by Asad Shahab Shafqat.

**The idea:** plant decoys (fake files, fake tools, fake credentials) in an AI agent's workspace. The company's own agent never needs them, so an agent that opens, uses or leaks one has probably been hijacked by hidden instructions. A Stackelberg security game decides how many decoys to plant, how realistic to make them, and where.

See [PLAN.md](PLAN.md) for the current status, decisions and to-do list.

## Status

Pilot stage. The code here is the feasibility pilot, not yet the finished decoy kit.

Pilot findings (106 agent runs in AgentDojo's workspace environment, Claude Haiku 5.5 and 4.5):

- 0 of 40 normal tasks raised an alarm when the alarm fires only if a decoy is opened, used or leaked. Counting any sighting of a decoy in a file listing would have flagged 9 of 40.
- 37 of 40 normal tasks completed with decoys present. The no-decoy baseline has not been run yet.
- Both models resisted all 48 built-in hidden-instruction attacks.
- Given the attacker's goal directly, an agent opened the fake passwords file in 2 runs, and the alarm fired both times.
- 3 runs that emailed the attacker without touching a decoy were not caught.

## Layout

| Path | Contents |
|---|---|
| `model/simple_model_check.py` | The deterrence threshold q* = V / (V + C), a toy realism trade-off, and a small multi-asset Stackelberg solver (linear programming). Illustrative numbers only. |
| `experiments/pilot/scripted_decoy_test.py` | Plants decoys in AgentDojo and runs scripted honest and hijacked agents. No AI model or API key needed. |
| `experiments/pilot/run_pilot.py` | Runs real Claude agents with decoys planted. Needs an API key and costs money. |
| `experiments/pilot/summarize_pilot.py` | Prints the counts above from the saved results. |
| `results/pilot/` | Raw results of the three pilot runs. |
| `decoykit/`, `attackers/`, `figures/`, `paper/` | Planned; empty for now. |

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
python model/simple_model_check.py
python experiments/pilot/scripted_decoy_test.py
python experiments/pilot/summarize_pilot.py
```

To run real agents, set your Anthropic API key first. Never put the key in a file inside this repo.

```bash
export ANTHROPIC_API_KEY="sk-ant-..."     # Windows PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-..."
python experiments/pilot/run_pilot.py
```

Options for `run_pilot.py`, set as environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `MODEL` | `claude-haiku-5-5` | Model to run |
| `KINDS` | `normal,attacked,direct` | Which run types to include |
| `OUT` | `pilot_run.json` | Where to save results |
| `SYS` | AgentDojo's default | Replacement system prompt |

The full default run is 73 agent runs and cost about $0.20 on Claude Haiku 5.5 in October 2026.

## Notes

- All data in AgentDojo is synthetic. The "attacker" address and the decoy contents are made up.
- `run_pilot.py` replaces AgentDojo's Anthropic request function, because AgentDojo 0.1.35 does not work with current versions of the Anthropic library as shipped.
