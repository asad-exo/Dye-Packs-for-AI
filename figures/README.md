# figures

Charts for the README, the slides and the report. Each chart comes in a light and a dark version (the README shows the one that matches the reader's GitHub theme).

Redraw them all with:

```powershell
python figures/charts.py
```

It reads the analysis files in `results/`. If the runs change, first run `python experiments/placement_comparison.py` and `python experiments/alarm_tradeoff.py`.

| File | What it shows | Data |
|---|---|---|
| `placement_loss_light.png`, `placement_loss_dark.png` | Expected loss against the number of decoys available, for four ways of placing them (the game's choice, the same number in every type, a random split, all on passwords), for Claude and Qwen3, when attacks are common and when they are rare | `results/placement_comparison.json` (model, with measured inputs) |
| `alarm_tradeoff_light.png`, `alarm_tradeoff_dark.png` | Thefts detected against false alarms on honest tasks, for each alarm rule and decoy setup, for naive and decoy-aware hijacked Qwen3 agents | `results/alarm_tradeoff.json` (measured directly) |

The colors are a fixed palette checked for color blindness and contrast in both versions. Each line also has its own marker shape, so the lines can be told apart without color.
