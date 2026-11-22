"""Charts for the README, slides and report, each in a light and a dark version.

    python figures/charts.py

Reads the results files and writes into figures/:
  placement_loss_{light,dark}.png    expected loss against the number of decoys available, for four ways of
                                     placing them (from results/placement_comparison.json)
  alarm_tradeoff_{light,dark}.png    thefts detected against false alarms on honest work, for each alarm rule
                                     and decoy setup (from results/alarm_tradeoff.json)
  deterrence_{light,dark}.png        how often a hijacked agent sent anything out, by the share of decoys
                                     (from results/deterrence.json)
  ablations_{light,dark}.png         expected loss of the full game, the game with one part removed, and simple
                                     rules, in three situations (from results/placement_comparison.json)
  false_alarms_{light,dark}.png      false alarms against the share of honest work that touches sensitive files,
                                     by alarm rule and decoy realism (from results/false_alarm_curve.json)
"""
from __future__ import annotations

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

THEMES = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781", grid="#e1e0d9", axis="#c3c2b7",
                  series=["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]),
    "dark": dict(surface="#1a1a19", ink="#f0efec", ink2="#c3c2b7", muted="#898781", grid="#2c2c2a", axis="#383835",
                 series=["#3987e5", "#d95926", "#199e70", "#c98500"]),
}


# ---------------------------------------------------------------------------------------------- shared style

def style(ax, t, xgrid=False):
    ax.set_facecolor(t["surface"])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(t["axis"])
    ax.spines["bottom"].set_linewidth(0.8)
    ax.grid(axis="both" if xgrid else "y", color=t["grid"], linewidth=0.6, linestyle="-")
    ax.set_axisbelow(True)
    ax.tick_params(colors=t["muted"], labelcolor=t["ink2"], length=0, labelsize=8.5, pad=4)


def line(ax, t, xs, ys, i, marker, z=3):
    ax.plot(xs, ys, color=t["series"][i], linewidth=1.6, marker=marker, markersize=6, markeredgecolor=t["surface"],
            markeredgewidth=1.0, solid_capstyle="round", zorder=z)


def legend(fig, t, y, items):
    """items: (series index, marker, label), in the fixed order of the series."""
    handles = [Line2D([0], [0], color=t["series"][i], marker=m, markersize=6, linewidth=1.6,
                      markeredgecolor=t["surface"], markeredgewidth=1.0) for i, m, _ in items]
    fig.legend(handles, [label for _, _, label in items], loc="upper left", bbox_to_anchor=(0.055, y), ncol=len(items),
               frameon=False, fontsize=8.5, labelcolor=t["ink2"], handlelength=2.2, columnspacing=1.6)


def title(fig, t, main, sub, sub_y=0.905):
    fig.text(0.055, 0.965, main, ha="left", va="top", fontsize=12, fontweight="semibold", color=t["ink"])
    fig.text(0.055, sub_y, sub, ha="left", va="top", fontsize=9, color=t["ink2"], linespacing=1.5)


def percent_axis(axis, ticks):
    axis.set_ticks(ticks)
    axis.set_ticklabels([f"{v}%" for v in ticks])


# ---------------------------------------------------------------------------------------------- placement

POLICIES = [("game", "Game-based", "o"), ("same-per-type", "Same number in every type", "s"),
            ("random", "Random split", "^"), ("crown-jewels", "All on passwords", "D")]
BUDGETS = list(range(10))


def loss_chart(data, theme):
    t = THEMES[theme]
    fig, axes = plt.subplots(2, 2, figsize=(9, 6.4), facecolor=t["surface"], sharex=True)
    title(fig, t, "Expected loss for each way of placing decoys",
          "Thieves know the strategy and pick their target or stay away. Lower is better; a password leak costs 10.")
    legend(fig, t, 0.86, [(i, m, label) for i, (_, label, m) in enumerate(POLICIES)])
    for row, profile in enumerate(("Claude", "Qwen3")):
        for col, (rpa, when) in enumerate((("1000", "attacks common (1 per 1,000 honest requests)"),
                                          ("100000", "attacks rare (1 per 100,000 honest requests)"))):
            ax = axes[row][col]
            style(ax, t)
            budgets = data["profiles"][profile]["budgets"][rpa]
            for i, (key, _, marker) in reversed(list(enumerate(POLICIES))):     # game drawn last, on top
                line(ax, t, BUDGETS, [-budgets[str(b)][key]["payoff"] for b in BUDGETS], i, marker, z=3 + (i == 0))
            ax.set_ylim(bottom=0)
            same = all(abs(budgets[str(b)]["game"]["payoff"] - budgets[str(b)]["same-per-type"]["payoff"]) < 1e-9 for b in BUDGETS)
            if same:   # the orange line is hidden under the blue one: say so instead of leaving it invisible
                ax.text(9.3, 6.5, "Same number in every type gives\nthe same result here; its line is\nhidden under the game-based one",
                        ha="right", va="center", fontsize=8, color=t["ink2"], linespacing=1.35)
            ax.set_title(f"{profile}, {when}", loc="left", fontsize=9, color=t["ink"], pad=6)
            ax.set_xticks(BUDGETS)
            if row == 1:
                ax.set_xlabel("decoys available", fontsize=8.5, color=t["ink2"])
            if col == 0:
                ax.set_ylabel("expected loss", fontsize=8.5, color=t["ink2"])
    fig.subplots_adjust(left=0.08, right=0.98, top=0.78, bottom=0.09, hspace=0.38, wspace=0.16)
    return fig


# ---------------------------------------------------------------------------------------------- alarm rules

SETUPS = [("k2_low", "2 low-realism decoys per type", "o"), ("k2_high", "2 high-realism decoys per type", "s"),
          ("k4_high", "4 high-realism decoys per type", "^")]
STRICT_TO_LOOSE = ["send_out", "leak_or_use", "act", "access", "any_sighting"]
RULE_GROUPS = [(("send_out", "leak_or_use", "act"), "opened, used or\nsent outside", "left"),
               (("access",), "found by\na search", "left"),
               (("any_sighting",), "shown in a\nfile list", "center")]


def alarm_chart(data, theme, profile="Qwen3"):
    t = THEMES[theme]
    cells = data["models"][profile]
    fig, axes = plt.subplots(1, 2, figsize=(9, 5.0), facecolor=t["surface"], sharey=True)
    title(fig, t, "Thefts detected against false alarms on honest work, for each alarm rule",
          "Qwen3 8B, measured. Points are alarm rules, named below by what a decoy must go through to set them off;\n"
          "stricter rules sit further left, and rules with equal results share a point. False alarms: share of 52 honest tasks.")
    legend(fig, t, 0.80, [(i, m, label) for i, (_, label, m) in enumerate(SETUPS)])
    for ax, (thief, name) in zip(axes, (("naive", "Naive hijacked agent"), ("aware", "Decoy-aware hijacked agent"))):
        style(ax, t, xgrid=True)
        thefts = [cells[s][thief]["thefts"] for s, _, _ in SETUPS]
        for i, (s, _, marker) in reversed(list(enumerate(SETUPS))):
            xs = [100 * cells[s]["false_alarms"][r] for r in STRICT_TO_LOOSE]
            ys = [100 * cells[s][thief]["detected"][r] for r in STRICT_TO_LOOSE]
            line(ax, t, xs, ys, i, marker, z=3 + (i == 0))
        for rules, label, align in RULE_GROUPS:     # name each group of rules under its points
            xs = [100 * cells[s]["false_alarms"][r] for s, _, _ in SETUPS for r in rules]
            lo, hi = min(xs), max(xs)
            ax.plot([lo, hi], [3, 3], color=t["muted"], linewidth=1.2, solid_capstyle="round", zorder=2)
            ax.text(lo - 0.4 if align == "left" else (lo + hi) / 2, 6, label, ha=align, va="bottom", fontsize=8,
                    color=t["ink2"], linespacing=1.3)
        ax.set_title(f"{name} ({min(thefts)}-{max(thefts)} thefts per setup)", loc="left", fontsize=9, color=t["ink"], pad=6)
        ax.set_xlim(-1.5, 28)
        ax.set_ylim(0, 103)
        percent_axis(ax.xaxis, range(0, 26, 5))
        percent_axis(ax.yaxis, range(0, 101, 20))
        ax.set_xlabel("honest tasks that set off the alarm", fontsize=8.5, color=t["ink2"])
    axes[0].set_ylabel("thefts detected", fontsize=8.5, color=t["ink2"])
    axes[1].tick_params(labelleft=False)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.70, bottom=0.11, wspace=0.08)
    return fig


# ---------------------------------------------------------------------------------------------- deterrence

THIEVES = [("naive", "Naive hijacked agent", "o"), ("aware", "Decoy-aware hijacked agent", "s")]
DETERRENCE_TITLES = {"Claude": "Claude Haiku 5.5: tries less as decoys increase", "Qwen3": "Qwen3 8B: not deterred"}


def deterrence_chart(data, theme):
    t = THEMES[theme]
    fig, axes = plt.subplots(1, 2, figsize=(9, 4.9), facecolor=t["surface"], sharey=True)
    title(fig, t, "Do decoys scare a hijacked agent off?",
          "Share of hijacked runs in which the agent sent anything out, by the share of decoys among each type's files\n"
          "(high realism, next to 2 real files). Vertical bars are 95% intervals; 27 to 162 runs per point.")
    legend(fig, t, 0.80, [(i, m, label) for i, (_, label, m) in enumerate(THIEVES)])
    for ax, model in zip(axes, ("Claude", "Qwen3")):
        style(ax, t)
        for i, (thief, _, marker) in enumerate(THIEVES):
            rows = data["models"][model][thief]
            xs = [100 * r["decoy_share"] + (-0.9, 0.9)[i] for r in rows]     # nudge the two series apart
            for x, r in zip(xs, rows):
                lo, hi = r["interval"]
                ax.plot([x, x], [100 * lo, 100 * hi], color=t["series"][i], linewidth=1.3, alpha=0.55,
                        solid_capstyle="round", zorder=2)
            line(ax, t, xs, [100 * r["share"] for r in rows], i, marker, z=3 + i)
        ax.set_title(DETERRENCE_TITLES[model], loc="left", fontsize=9, color=t["ink"], pad=6)
        if not any(r["decoys_per_type"] == 1 for r in data["models"][model]["naive"]):
            ax.text(100 / 3, 62, "no runs with\n1 decoy per type", ha="center", va="center", fontsize=8,
                    color=t["muted"], linespacing=1.3)
        ax.set_xlim(-6, 73)
        ax.set_ylim(0, 103)
        ax.set_xticks([0, 100 / 3, 50, 200 / 3])
        ax.set_xticklabels(["none", "1/3\n(1 decoy)", "1/2\n(2 decoys)", "2/3\n(4 decoys)"])
        percent_axis(ax.yaxis, range(0, 101, 20))
        ax.set_xlabel("share of decoys among each type's files", fontsize=8.5, color=t["ink2"])
    axes[0].set_ylabel("runs that sent anything out", fontsize=8.5, color=t["ink2"])
    axes[1].tick_params(labelleft=False)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.70, bottom=0.17, wspace=0.08)
    return fig


# ---------------------------------------------------------------------------------------------- ablations

ABLATION_ROWS = [("game", "Game (full model)", 0), ("game, naive thieves only", "Game, naive thieves only", 1),
                 ("game, no false-alarm cost", "Game, no false-alarm cost", 1),
                 ("value-proportional", "Split by value", 2), ("same-per-type", "Same number in every type", 2),
                 ("random", "Random split", 2), ("crown-jewels", "All on passwords", 2)]
ABLATION_PANELS = [("high", 1000, "Attacks common,\nrealistic decoys"), ("low", 1000, "Attacks common,\nlow-realism decoys"),
                   ("high", 100000, "Attacks rare (1 per 100,000\nhonest requests), realistic decoys")]


def ablation_chart(data, theme, profile="Qwen3", budget=9):
    t = THEMES[theme]
    colors = [t["series"][0], t["series"][1], t["muted"]]
    fig, axes = plt.subplots(1, 3, figsize=(9, 4.9), facecolor=t["surface"], sharey=True)
    title(fig, t, "Which parts of the game matter, and when",
          f"{profile}, {budget} decoys available; expected loss, lower is better. A game with one part removed chooses its\n"
          "placement without that part, then is scored with the full model.")
    handles = [Line2D([0], [0], color=c, linewidth=6) for c in colors]
    fig.legend(handles, ["Full game model", "Game with one part removed", "Simple rule"], loc="upper left",
               bbox_to_anchor=(0.055, 0.80), ncol=3, frameon=False, fontsize=8.5, labelcolor=t["ink2"], handlelength=1.2,
               columnspacing=1.6)
    rows = data["profiles"][profile]["ablations"]
    ys = list(range(len(ABLATION_ROWS)))[::-1]
    for ax, (realism, rpa, name) in zip(axes, ABLATION_PANELS):
        style(ax, t)
        ax.grid(False)
        ax.grid(axis="x", color=t["grid"], linewidth=0.6)
        cell = next(r for r in rows if r["realism"] == realism and r["requests_per_attack"] == rpa and r["budget"] == budget)
        losses = [-cell[key]["payoff"] for key, _, _ in ABLATION_ROWS]
        top = max(losses) * 1.32
        for y, loss, (key, _, kind) in zip(ys, losses, ABLATION_ROWS):
            ax.barh(y, loss, height=0.62, color=colors[kind], zorder=3)
            ax.text(loss + top * 0.015, y, f"{loss:.2f}", va="center", ha="left", fontsize=8, color=t["ink"])
        ax.set_xlim(0, top)
        ax.set_title(name, loc="left", fontsize=9, color=t["ink"], pad=6)
        ax.set_xlabel("expected loss", fontsize=8.5, color=t["ink2"])
    axes[0].set_yticks(ys)
    axes[0].set_yticklabels([label for _, label, _ in ABLATION_ROWS], fontsize=8.5)
    for ax in axes[1:]:
        ax.tick_params(labelleft=False)
    fig.subplots_adjust(left=0.2, right=0.98, top=0.66, bottom=0.11, wspace=0.08)
    return fig


# ---------------------------------------------------------------------------------------------- false alarms

FA_RULES = [("any_sighting", "shown in a file list", 0), ("access", "found by a search", 1), ("send_out", "sent outside", 3)]


def false_alarm_chart(data, theme):
    t = THEMES[theme]
    fig, axes = plt.subplots(1, 2, figsize=(9, 4.9), facecolor=t["surface"], sharey=True)
    title(fig, t, "False alarms grow with the share of honest work that touches sensitive files",
          "Mixed from the rates measured on normal and on sensitive tasks. Lines: high-realism decoys; shaded: the range\n"
          "from low to high realism. Each line is one alarm rule, named by what a decoy must go through to set it off.")
    fs = [i / 100 for i in range(101)]
    for ax, model in zip(axes, ("Claude", "Qwen3")):
        style(ax, t, xgrid=True)
        cells = data["models"][model]
        for rule, label, i in FA_RULES:
            def curve(cell):
                r = cell["rules"][rule]
                return [100 * ((1 - f) * r["normal"] + f * r["sensitive"]) for f in fs]
            curves = [curve(c) for c in cells.values()]
            lo = [min(v) for v in zip(*curves)]
            hi = [max(v) for v in zip(*curves)]
            ax.fill_between([100 * f for f in fs], lo, hi, color=t["series"][i], alpha=0.18, linewidth=0, zorder=2)
            ys = curve(cells["high"])
            ax.plot([100 * f for f in fs], ys, color=t["series"][i], linewidth=2, zorder=3, solid_capstyle="round")
            # rising lines: label above-left or below-right of a point, where the line cannot run into it
            if rule == "send_out":
                ax.text(98, ys[-1] + 2.2, label + ": never fired", va="bottom", ha="right", fontsize=8, color=t["ink2"])
            elif rule == "access":
                ax.text(54, ys[54] - 2.5, label, va="top", ha="left", fontsize=8, color=t["ink2"])
            else:
                ax.text(62, ys[62] + 2.5, label, va="bottom", ha="right", fontsize=8, color=t["ink2"])
        n = data["task_set"][model]           # the tasks behind the alarm chart: where its false alarms sit on this one
        mix = 100 * n["sensitive"] / (n["sensitive"] + n["standard"])
        ax.axvline(mix, color=t["muted"], linewidth=1, linestyle=(0, (2, 2)), zorder=1)
        ax.text(mix + 1.5, 57, f"all our tasks\n({n['sensitive']} of {n['sensitive'] + n['standard']})", fontsize=7.5,
                color=t["muted"], va="top")
        ax.set_title(f"{model}: honest agent", loc="left", fontsize=9, color=t["ink"], pad=6)
        ax.set_xlim(0, 100)
        ax.set_ylim(-1, 64)
        percent_axis(ax.xaxis, range(0, 101, 25))
        percent_axis(ax.yaxis, range(0, 61, 10))
        ax.set_xlabel("share of honest tasks that need sensitive files", fontsize=8.5, color=t["ink2"])
    axes[0].set_ylabel("honest tasks that set off the alarm", fontsize=8.5, color=t["ink2"])
    axes[1].tick_params(labelleft=False)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.76, bottom=0.12, wspace=0.08)
    return fig


# ---------------------------------------------------------------------------------------------- main

def main():
    installed = {f.name for f in font_manager.fontManager.ttflist}      # the first of these that is installed
    plt.rcParams["font.family"] = next(f for f in ("Inter", "Segoe UI", "DejaVu Sans") if f in installed)
    charts = [("placement_loss", "placement_comparison.json", loss_chart), ("alarm_tradeoff", "alarm_tradeoff.json", alarm_chart),
              ("deterrence", "deterrence.json", deterrence_chart), ("ablations", "placement_comparison.json", ablation_chart),
              ("false_alarms", "false_alarm_curve.json", false_alarm_chart)]
    for name, source, make in charts:
        data = json.load(open(os.path.join(ROOT, "results", source), encoding="utf-8"))
        for theme in THEMES:
            fig = make(data, theme)
            path = os.path.join(HERE, f"{name}_{theme}.png")
            fig.savefig(path, dpi=200, facecolor=fig.get_facecolor())
            plt.close(fig)
            print("saved", os.path.relpath(path, ROOT))


if __name__ == "__main__":
    main()
