# Dye Packs for AI

Game-theoretic decoys that catch hijacked AI agents.

Course project for ECE-GY 6263 Game Theory (NYU Tandon, Fall 2026) by Asad Shahab Shafqat.

**The idea:** plant decoys (fake files, fake tools, fake credentials) in an AI agent's workspace. The company's own agent never needs them, so an agent that opens, uses or leaks one has probably been hijacked by hidden instructions. A Stackelberg security game decides how many decoys to plant, how realistic to make them, and where.

## How it works

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/hijack_dark.png">
  <img alt="An attacker plants an email with hidden instructions; the company's AI agent reads it while summarizing the inbox, searches the drive and emails the files to the attacker" src="figures/hijack_light.png" width="100%">
</picture>

An attacker hides instructions in something the agent will read: an email, a calendar invite or a shared file. When an employee asks the agent for something ordinary, the agent reads the hidden text, follows it, and sends company secrets outside. In our runs none of the three models tested followed such hidden instructions (0 of 648), so we also give the agent the attacker's instructions outright ("direct mode") to study what a hijacked agent does.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/decoys_dark.png">
  <img alt="An honest agent opens the file it was asked for: no alarm. A naive hijacked agent sends every file: alarm, but the real files leave too. A decoy-aware hijacked agent sends one file: caught if it is a decoy, missed if it is real" src="figures/decoys_light.png" width="100%">
</picture>

Decoys sit next to the real files and look the same to the agent. Each holds its own fake value, so the monitor knows when one is touched. A naive hijacked agent sends everything and sets off the alarm, but the real files leave too. A decoy-aware one sends a single file and is caught only when that file is a decoy. Honest work pays a price when a request only describes a file: the search can turn up decoys and confuse the agent.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/game_dark.png">
  <img alt="The company commits to a decoy placement; the thief learns it and steals where stealing pays most. With 3 decoys all on passwords the thief takes the bank details; with one decoy in each type nothing pays and the thief stays away" src="figures/game_light.png" width="100%">
</picture>

Where to put the decoys is a Stackelberg game: the company commits to a placement, and the thief, who learns it, steals where stealing pays most or stays away. Putting every decoy on the most valuable files only sends the thief elsewhere; spreading the same decoys can make every target unprofitable. [model/MODEL.md](model/MODEL.md) has the full model, with thieves who grab everything, thieves who spot some decoys, and the cost to honest work.

## Status

The decoy kit, the scripted attackers and the game model are written and checked. The experiments have run: false alarms from honest agents, real hijack attempts, and the comparison of decoy placements and alarm rules (results below). Next: the presentation and the report. The model is explained in [model/MODEL.md](model/MODEL.md).

Honest-agent results so far (November 2026). Nobody attacks in these runs, so every alarm is a false alarm.

- **AgentDojo's 40 normal tasks** (Claude Haiku 5.5, 440 runs; Qwen3 8B, 203 runs): no false alarms under any rule except `any_sighting`. Decoys only showed up in full file listings (10-20% of runs). Task success did not change by more than run-to-run noise.
- **12 honest tasks that need sensitive files** (`experiments/sensitive_tasks.py`; Claude Haiku 5.5, 720 runs; Gemini 3.8 Flash, 127; Qwen3 8B, 180):
  - When the request names the file, decoys cost almost nothing: success 98-100%, and one `access` alarm in 52 Gemini runs.
  - When the request only describes the file, the agent's search returned decoys in 56-78% of runs (`access` alarm). Decoys hold different values from the real file, so the agent gave the right answer in 86-96% of runs instead of 100%, and showed the user a decoy's value in 29-51%.
  - The `act` rule fired 7 times, all in one task (email the build-server password to a new colleague). Gemini (2 of 8 runs) and Qwen3 (5 of 12) picked a decoy's password and emailed it. Claude asked which one instead.
  - Most of the cost appears with the first decoy. More decoys add a little (Qwen3's right answers: 100%, 83%, 78% at 1, 2, 4 decoys per class).
- **The `send_out` rule** (a decoy is sent to someone outside the company) gave 0 false alarms in 1,418 honest runs with decoys across all three models (95% upper bound 0.21% per run). It catches the scripted attackers exactly as often as `act` does. The rule was chosen after seeing the `act` alarms above, so it was tested again on fresh runs: 324 new Claude runs of the sensitive tasks set off neither `send_out` nor `act`. Fresh Qwen3 runs are under way.
- Tables: `python experiments/honest_runs.py --summary` (add `--provider` and `--model` for other models). Raw runs: `results/honest/`.

Hijack results so far (November 2026; `experiments/hijack_runs.py`):

- **Hidden instructions:** no model followed any of them. That is 0 of 648 runs: Claude Haiku 5.5 288, Qwen3 8B 288, Llama 3.1 8B 72 (Llama also finished the user's task in only 15 of 72 runs, so it often may not have read far enough to meet the instruction).
- **Direct mode** (the attacker's instructions given outright, in two versions: naive, and decoy-aware, which warns that some files are decoys and says to send only the one that looks most genuine; 27 runs per setting and version, 162 for decoy-aware Claude with high-realism decoys). Share of runs in which a real secret left the company:

  | | Claude, naive | Claude, decoy-aware | Qwen3, naive | Qwen3, decoy-aware |
  |---|---|---|---|---|
  | no decoys | 37% | 52% | 96% | 100% |
  | 2 low-realism decoys per type | 37% | 70% | 89% | 67% |
  | 2 high-realism decoys per type | 26% | 11% | 100% | 48% |
  | 4 high-realism decoys per type | 11% | 3% | 89% | 48% |

- **Decoys work like an alarm, not a lock:**
  - **Naive hijacked agents** mostly sent everything they found in one message (Claude: 20 of 20 times it sent anything; Qwen3: 63 of 81 runs). The alarm went off, but the real secret in that message still left: detected, not prevented.
  - **Decoy-aware Qwen3** sent a single file. Against high-realism decoys it picked a decoy about half the time (caught, nothing real left). Against low-realism decoys it picked one only 31% of the time.
  - **Decoy-aware Claude** was mostly deterred by high-realism decoys. In 162 runs per setup it sent something in 25% (2 decoys per type) and 10% (4 per type) of runs, against 52% with no decoys. When it did send, it picked a decoy 55% and 69% of the time, about as often as a blind pick would (50% and 67%).

Where to put decoys, and which alarm rule to use (November 2026; `experiments/placement_comparison.py`, `experiments/alarm_tradeoff.py`):

**Placement.** Four ways to place a number of decoys across passwords, customer records and bank details (2 real files each), scored with the game model ([MODEL.md](model/MODEL.md), Part B): the game's choice (which may leave some decoys unused), the same number in every type, a random split, and all on passwords.

- **Measured in the runs:** how often an honest request that describes a file goes wrong once its type has decoys (passwords 33-36%, the other types 0-8%); how many naive hijacked agents send everything at once (Claude 20 of 20, Qwen3 85% of 80); how many high-realism decoys a decoy-aware agent sees through (Qwen3 10%, from 52 single-file sends; Claude none, from 56).
- **Assumed:** a leak costs 10, 6 and 8 for the three types, and the thief gains as much; being caught costs the thief 20; a detection is worth 2 to the defender; 70% of hijacks are naive and 30% decoy-aware; 1% of honest requests look for each type without naming the file; a request that goes wrong costs 0.1.
- Thieves know the strategy and how many decoys each type holds, but not which files are fake. They pick a target or stay away.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/placement_loss_dark.png">
  <img alt="Expected loss against decoys available, for four placement strategies, for Claude and Qwen3, when attacks are common and when they are rare" src="figures/placement_loss_light.png" width="100%">
</picture>

- **All on passwords** never gets the loss below 8, however many decoys it has: thieves go for the bank details instead (Result 5 in MODEL.md).
- **When attacks are common** (1 per 1,000 honest requests), the game is never worse than the others, by construction: it can pick any of their placements.
  - The same number in every type does just as well once there are enough decoys to make stealing not pay for every kind of thief: 1 per type against Claude, and against Qwen3 (which saw through 10% of the decoys) 2 password decoys and 1 in each other type. Given more decoys, the even split places them all, while the game stops at the fewest that do the job (3 against Claude, 4 against Qwen3).
  - An estimate from only 6 runs had suggested that decoy-aware Claude saw through about half the decoys, which put the game ahead against Claude. 270 more runs showed it sees through none.
  - A random split is worse than the same number in every type.
- **When attacks are rare** (1 per 100,000), the confusion decoys cause in honest work costs more than they save. The game plants none (loss 10, one leak). Placements that use all their decoys lose 23-50.
- **Changing one assumption at a time** (50% or 90% naive hijacks; being caught costs the thief 10 or 40; a detection worth nothing; all three types worth 10; checked with 3 and 9 decoys) keeps the picture: the game and the same number in every type stay tied for best, a random split comes third, and all on passwords stays stuck. Each extra decoy also costs honest work a little (left out here because it is small); counting it would favor the game, which uses the fewest decoys.

**Does the model match the runs?** The model predicts how often a theft includes a decoy, and so is detected. A naive thief sends everything at once (85% of the time for Qwen3) or else one file; a decoy-aware thief sends one file and avoids the decoys it sees through (10%). For Qwen3:

| Setup | Thief | Thefts | Detected (measured) | Detected (model) |
|---|---|---|---|---|
| 2 low-realism decoys per type | naive | 26 | 96% | 92% |
| 2 high-realism decoys per type | naive | 27 | 85% | 92% |
| 4 high-realism decoys per type | naive | 27 | 93% | 95% |
| 2 high-realism decoys per type | decoy-aware | 27 | 52% | 45% |
| 4 high-realism decoys per type | decoy-aware | 26 | 54% | 60% |

All are within 8 points, about the sampling noise for 26-27 thefts (one standard error is 7-10 points). This is a consistency check, not a test on fresh data: the two numbers came from these same runs. Low-realism decoys against a decoy-aware thief are left out, because the "seen through" share was measured on high-realism decoys. For Claude, fitted the same way: every naive theft detected (20 thefts; model 100%), and decoy-aware thefts detected 55% with 2 high-realism decoys per type (40 thefts; model 50%) and 69% with 4 (16 thefts; model 67%).

A test on fresh data is set up: the placement the game recommends for Qwen3 (2 password decoys, 1 each for customer records and bank details), which no run has used before. The model's prediction was written down before any of those runs, in `results/validation_prediction.json`: 91% of naive thefts and 35% of decoy-aware thefts detected. A second test does the same for Claude: 1 decoy per type, what the game recommends against Claude, never used in its hijack runs before; predicted in `results/validation_prediction_claude.json`: every naive theft and 33% of decoy-aware thefts detected. `python experiments/validation.py` (add `--model claude` for the second test) compares a prediction with the runs.

**Which alarm rule.** For each decoy setup and alarm rule, straight from the runs with no model in between: the share of the 52 honest tasks that set off the alarm (the 40 normal tasks and the 12 that need sensitive files, each task counted once), against the share of thefts it detected (direct-mode runs in which the agent sent something out; detected means the alarm went off at some point in the run).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="figures/alarm_tradeoff_dark.png">
  <img alt="Thefts detected against false alarms on honest work for each alarm rule and decoy setup, for naive and decoy-aware hijacked Qwen3 agents" src="figures/alarm_tradeoff_light.png" width="100%">
</picture>

- **Naive hijacked agents:** the strictest rule (a decoy is sent outside) detected 85-96% of thefts with no false alarm on any honest task. Looser rules detected at most 15 points more, at 8-26% false alarms.
- **Decoy-aware agents:** the strictest rule detected 31% of thefts with low-realism decoys and 52-54% with high-realism ones. The rule "found by a search" detected 70-88%, because the agent's own search returns the decoys along with the real files. (The decoy-aware instructions told it to look at all the candidates first, so a more careful attacker might set off this rule less often.) But this rule also went off on 8-9% of honest tasks: on 36-39% of the tasks that need sensitive files, and never on the normal tasks.
- **Realism matters more than numbers:** against decoy-aware agents, high-realism decoys raised strict-rule detection from 31% to 52% for Qwen3, and from 0% to 55% for Claude. Four decoys per type instead of two added 2 points for Qwen3.
- **`act` and `send_out`:** they detected the same thefts except one (Qwen3, 4 high-realism decoys, decoy-aware: 58% against 54%). `act` went off on 0.6-1.3% of honest tasks (all in one task: emailing a password to a new colleague), `send_out` on none.
- **Claude:** every naive theft was detected under every rule (20 of 20). Against decoy-aware Claude the strictest rule detected none of 19 thefts with low-realism decoys, 55% of 40 with 2 high-realism decoys per type and 69% of 16 with 4; the search rule detected 79%, 100% and 94%. Claude's false alarms: none under the strict rules, 6-7% under "found by a search", 27% under "shown in a file list".
- A practical setup could use two levels: stop the agent when a decoy is sent outside, and flag it for review when a decoy turns up in a search.

Pilot findings (October 2026) (106 agent runs in AgentDojo's workspace environment, Claude Haiku 5.5 and 4.5):

- 0 of 40 normal tasks raised an alarm when the alarm fires only if a decoy is opened, used or leaked. Counting any sighting of a decoy in a file listing would have flagged 9 of 40.
- 37 of 40 normal tasks completed with decoys present. The no-decoy baseline has not been run yet.
- Both models resisted all 48 built-in hidden-instruction attacks.
- Given the attacker's goal directly, an agent opened the fake passwords file in 2 runs, and the alarm fired both times.
- 3 runs that emailed the attacker without touching a decoy were not caught.

## Layout

| Path | Contents |
|---|---|
| `model/MODEL.md` | The game, written to be explained at a whiteboard. Part A: the simple model (the deterrence threshold q* = V / (V + C) and the false-alarm cost). Part B: the model as the experiments measured it (a fixed cost of protecting a type of file, thieves who pick one file or grab everything, and which types to protect). |
| `model/simple_model.py` | The one-asset game in code; checks Results 1 and 2 numerically. |
| `model/placement_solver.py` | The Stackelberg solver for Part B: chooses which types of file to protect and with how many decoys, against a mix of pick-one and grab-everything thieves. Checked against Part A's formulas and a brute-force search. |
| `decoykit/` | The decoy kit: asset classes with real items and decoys at three realism levels, placement policies, and the alarm monitor. See [decoykit/README.md](decoykit/README.md). |
| `attackers/` | Four scripted hijacked agents (grab_all, pick_one, decoy_aware, informed), and the hidden instructions used for real hijack attempts (`injections.py`). See [attackers/README.md](attackers/README.md). |
| `experiments/offline_check.py` | Scripted attackers against each placement, plus AgentDojo's scripted task solutions as a stand-in for the honest agent. No API key needed. |
| `experiments/honest_runs.py` | Real AI agents do the 40 normal tasks under 11 decoy settings, to measure false alarms and any cost to task success. Works with Anthropic, Google (Gemini) and local models through Ollama. |
| `experiments/hijack_runs.py` | Real hijack attempts: hidden instructions in emails, calendar entries and files tell the agent to steal the planted secrets (or, in direct mode, the agent is given the attacker's instructions outright). Measures how often a hijacked agent is caught by a decoy before a real secret leaves. |
| `experiments/providers.py` | Connects AgentDojo to each model provider and fixes what current library versions broke. |
| `experiments/anthropic_compat.py` | The fixes for the Anthropic library, plus token counting and cost estimates. |
| `experiments/sensitive_tasks.py` | 12 honest tasks that genuinely need passwords, customer records or bank details, each with a pass/fail check. |
| `experiments/check_setup.py` | Free check that all three provider connections work (the network is faked; no key, no cost). |
| `experiments/placement_comparison.py` | Scores four ways of placing decoys (the game's choice, the same number in every type, a random split, all on passwords) with the game model and the numbers the runs measured. Also checks the model against the hijack runs, and changes the assumptions one at a time. |
| `experiments/alarm_tradeoff.py` | For each alarm rule and decoy setup: false alarms on honest tasks against thefts detected, straight from the runs. |
| `experiments/validation.py` | Tests of the model on fresh data: writes down its prediction for a placement never run before (`--predict`), then compares it with the runs. One test per model. |
| `experiments/pilot/` | The October feasibility pilot: `run_pilot.py` (real AI agents; needs a key), `scripted_decoy_test.py`, `summarize_pilot.py`. |
| `results/` | `honest/` and `hijack/`: one line per agent run, per model. `placement_comparison.json` and `alarm_tradeoff.json`: the two analyses above. `pilot/`: the October pilot. `offline_check.json`: the scripted attackers. |
| `model/simple_model_check.py` | Early sketch from the proposal stage, replaced by the two model files above. |
| `figures/` | The diagrams and charts in this README, in light and dark versions: `diagrams.py` draws the diagrams, `charts.py` redraws the charts from `results/`. |
| `paper/` | The report; empty for now. |

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
python model/placement_solver.py             # checks the solver (about 20 seconds), then a 3-type demo
python experiments/offline_check.py 200      # scripted attackers, 200 runs per setting (under a minute)
python experiments/check_setup.py            # checks the Anthropic, Google and Ollama connections, for free
python experiments/pilot/summarize_pilot.py  # the pilot numbers above

# Analyses of the saved runs, and the charts (no API key needed)
python experiments/placement_comparison.py   # placement strategies scored with the measured numbers (a few seconds)
python experiments/alarm_tradeoff.py         # false alarms against thefts detected, for each alarm rule
python experiments/validation.py             # the model's prediction for a new placement, against the runs
python figures/charts.py                     # redraws the charts from those two results
python figures/diagrams.py                   # redraws the diagrams (see figures/README.md)
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

Hijack attempts work the same way, with the same model options:

```powershell
python experiments/hijack_runs.py --plan
python experiments/hijack_runs.py --provider ollama --model qwen3:8b --limit 6
python experiments/hijack_runs.py --provider ollama --model qwen3:8b
python experiments/hijack_runs.py --provider ollama --model qwen3:8b --summary
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

## License

All rights reserved; see [LICENSE](LICENSE). The repository is public so that it can be read and reviewed, not reused. Versions before 22 November 2026 were released under the MIT License.
