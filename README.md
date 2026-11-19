# Dye Packs for AI

Game-theoretic decoys that catch hijacked AI agents.

Course project for ECE-GY 6263 Game Theory (NYU Tandon, Fall 2026) by Asad Shahab Shafqat.

**The idea:** plant decoys (fake files, fake tools, fake credentials) in an AI agent's workspace. The company's own agent never needs them, so an agent that opens, uses or leaks one has probably been hijacked by hidden instructions. A Stackelberg security game decides how many decoys to plant, how realistic to make them, and where.

## Status

Building. The decoy kit, the scripted attackers and the game model are written and checked offline. Next: measure how often real AI agents set off false alarms, then compare decoy placements. The model is explained in [model/MODEL.md](model/MODEL.md).

Honest-agent results so far (November 2026). Nobody attacks in these runs, so every alarm is a false alarm.

- **AgentDojo's 40 normal tasks** (Claude Haiku 5.5, 440 runs; Qwen3 8B, 203 runs): no false alarms under the `access`, `act` or `leak_or_use` rules. Decoys only showed up in full file listings (`any_sighting`: 10-20% of runs). Task success did not change by more than run-to-run noise.
- **12 honest tasks that need sensitive files** (`experiments/sensitive_tasks.py`; Claude Haiku 5.5, 3 repeats, 360 runs):
  - When the request names the file, there were no false alarms and no lost tasks.
  - When the request only describes the file, the agent's search returned decoys in about 55% of runs (an `access` alarm). Decoys hold different values from the real file, so the agent gave the right answer in 83-93% of runs instead of 100%, and showed the user a decoy's value in about half.
  - None of these costs grew much with the number of decoys (1, 2 or 4 per class).
- **The `act` rule (open, use or send a decoy) never fired on an honest agent:** 0 of 849 runs with decoys across all models (95% upper bound: 0.35% per run).
- Tables: `python experiments/honest_runs.py --summary` (add `--provider` and `--model` for other models). Raw runs: `results/honest/`.

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
| `experiments/honest_runs.py` | Real AI agents do the 40 normal tasks under 11 decoy settings, to measure false alarms and any cost to task success. Works with Anthropic, Google (Gemini) and local models through Ollama. |
| `experiments/providers.py` | Connects AgentDojo to each model provider and fixes what current library versions broke. |
| `experiments/anthropic_compat.py` | The fixes for the Anthropic library, plus token counting and cost estimates. |
| `experiments/sensitive_tasks.py` | 12 honest tasks that genuinely need passwords, customer records or bank details, each with a pass/fail check. |
| `experiments/check_setup.py` | Free check that all three provider connections work (the network is faked; no key, no cost). |
| `experiments/pilot/` | The October feasibility pilot: `run_pilot.py` (real AI agents; needs a key), `scripted_decoy_test.py`, `summarize_pilot.py`. |
| `results/` | Raw results: `pilot/` from October, `offline_check.json` from the scripted attackers. |
| `model/simple_model_check.py` | Early sketch from the proposal stage, replaced by the two model files above. |
| `figures/`, `paper/` | Charts and the report; empty for now. |

## Setup

Requires Python 3.10 or newer (tested on 3.13 and 3.14). The commands below are for Windows PowerShell; on macOS or Linux use `source .venv/bin/activate` to activate and `export NAME=value` to set variables.

```powershell
git clone https://github.com/asad-exo/Dye-Packs-for-AI
cd Dye-Packs-for-AI
python -m venv .venv
.venv\Scripts\Activate.ps1          # run this in every new terminal
pip install -r requirements.txt
setx PYTHONUTF8 1                    # avoids Windows text-encoding errors (new terminals)
```

If PowerShell says running scripts is disabled, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and answer Y.

### Local models (optional): Ollama

1. Update the NVIDIA driver; `nvidia-smi` should list the GPU.
2. Install Ollama from [ollama.com](https://ollama.com).
3. Give the model room for long conversations, then quit and reopen Ollama:
   ```powershell
   setx OLLAMA_CONTEXT_LENGTH 16384     # each agent step is about 8,000 tokens; the default is smaller
   setx OLLAMA_FLASH_ATTENTION 1        # these two shrink that memory so an 8B model fits in 8 GB
   setx OLLAMA_KV_CACHE_TYPE q8_0
   ```
4. Download and test a model that supports tools:
   ```powershell
   ollama pull qwen3:8b
   ollama show qwen3:8b                 # "tools" should be listed under Capabilities
   ollama run qwen3:8b "Say hi in five words"
   ollama ps                            # PROCESSOR should say 100% GPU
   ```

### API keys (only for the models you use)

Keys live in environment variables on your own computer. Never put a key in a file inside this repo.

- **Anthropic:** create a key in the Anthropic Console (set a monthly spend limit first) and store it as `ANTHROPIC_API_KEY`.
- **Google Gemini:** create a key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey) and store it as `GEMINI_API_KEY`. The free tier has daily request limits, shown on AI Studio's rate-limit page; a full pass may need a few days or billing turned on.

To store a key on Windows, search for "Edit environment variables for your account", click New, enter the name and the key, then open a new terminal. This keeps the key out of your command history.

## Run

Run everything from the repository's top folder.

```powershell
# No API key needed
python model/simple_model.py                 # checks Results 1 and 2
python model/placement_solver.py             # solver demo: game placement vs. even and top-only
python experiments/offline_check.py 200      # scripted attackers, 200 runs per setting (under a minute)
python experiments/check_setup.py            # checks the Anthropic, Google and Ollama connections, for free
python experiments/pilot/summarize_pilot.py  # the pilot numbers above
```

Honest-agent runs. Start with `--plan` (spends nothing) and `--limit 5` (a 5-run test) for any new model.

```powershell
# Anthropic (default model claude-haiku-5-5): about $1.20 for a full pass of 440 runs
python experiments/honest_runs.py --plan
python experiments/honest_runs.py --limit 5
python experiments/honest_runs.py

# Local model through Ollama: free, one run at a time; a full pass takes hours
python experiments/honest_runs.py --provider ollama --model qwen3:8b --limit 5

# Gemini: give the exact model name, and its price per million input,output tokens from Google's price list
python experiments/honest_runs.py --provider google --model <model-name> --price 0.30,2.50 --limit 5

# Tables of false alarms and task success (add the same --provider and --model)
python experiments/honest_runs.py --summary
```

Each run is saved as one line in `results/honest/<model>.jsonl` as soon as it finishes, so a run can be stopped (Ctrl+C) and restarted: it picks up where it left off. It stops by itself at the cost limit (`--max-cost`, default $5) and after 5 failures in a row to reach the model.

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
- AgentDojo 0.1.35 does not work with current versions of the Anthropic library as shipped. `experiments/anthropic_compat.py` and `experiments/providers.py` fix the problems found so far, for each provider; every script that runs a model imports them first.
- Figures explaining the project (how hijacking works, how decoys catch it, the game, the results) will be added to this README as the experiments finish.
