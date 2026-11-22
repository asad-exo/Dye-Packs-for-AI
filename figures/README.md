# figures

Diagrams and charts for the README, the slides and the report. Each comes in a light and a dark version (the README shows the one that matches the reader's GitHub theme).

## Diagrams

| File | What it shows |
|---|---|
| `hijack_light.png`, `hijack_dark.png` | How an AI agent gets hijacked: hidden instructions in an email take over, and the agent sends company files to the attacker |
| `decoys_light.png`, `decoys_dark.png` | How decoys catch a hijacked agent: what an honest agent, a naive thief and a decoy-aware thief send, and when the alarm fires |
| `game_light.png`, `game_dark.png` | The decoy game: who moves first, and the same 3 decoys placed two ways (the thief's gain from each type of file) |

`diagrams.py` draws them as SVG and turns them into PNG with Playwright. To redraw them:

```powershell
pip install playwright
playwright install chromium
python figures/diagrams.py
```

Without Playwright, the script saves `.svg` files instead, which any web browser opens.

## Charts

| File | What it shows | Data |
|---|---|---|
| `placement_loss_light.png`, `placement_loss_dark.png` | Expected loss against the number of decoys available, for four ways of placing them (the game's choice, the same number in every type, a random split, all on passwords), for Claude and Qwen3, when attacks are common and when they are rare | `results/placement_comparison.json` (model, with measured inputs) |
| `alarm_tradeoff_light.png`, `alarm_tradeoff_dark.png` | Thefts detected against false alarms on honest tasks, for each alarm rule and decoy setup, for naive and decoy-aware hijacked Qwen3 agents | `results/alarm_tradeoff.json` (measured directly) |
| `deterrence_light.png`, `deterrence_dark.png` | How often a hijacked agent sent anything out, by the share of decoys among each type's files, for Claude and Qwen3 | `results/deterrence.json` (measured directly) |

Redraw them with `python figures/charts.py`. It reads the analysis files in `results/`; if the runs change, first run `python experiments/placement_comparison.py`, `python experiments/alarm_tradeoff.py` and `python experiments/deterrence.py`.

The colors are a fixed palette checked for color blindness and contrast in both versions. Each chart line also has its own marker shape, so the lines can be told apart without color.
