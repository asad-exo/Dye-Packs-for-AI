"""Diagrams that explain the project, each in a light and a dark version.

    python figures/diagrams.py

Writes into figures/:
  hijack_{light,dark}.png    how an AI agent gets hijacked
  decoys_{light,dark}.png    how decoys catch a hijacked agent: the honest agent, a naive thief, a decoy-aware thief
  game_{light,dark}.png      the decoy game: who moves first, and the same 3 decoys placed two ways

The drawings are SVG, written by this script. Turning them into PNG needs Playwright with its Chromium browser
(pip install playwright, then playwright install chromium); without it the script saves the .svg files instead,
which any web browser can open.
"""
from __future__ import annotations

import html
import os

HERE = os.path.dirname(os.path.abspath(__file__))

THEMES = {   # the same palette as figures/charts.py
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781", line="#c3c2b7", faint="#ecebe6",
                  blue="#2a78d6", orange="#eb6834"),
    "dark": dict(surface="#1a1a19", ink="#f0efec", ink2="#c3c2b7", muted="#898781", line="#5b5a56", faint="#262624",
                 blue="#3987e5", orange="#d95926"),
}
FONT = "Inter, 'Segoe UI', Arial, sans-serif"

# Thief's gain from one type of file, for a thief who sends one file (MODEL.md, Part A):
# (1 - q) * V - q * C, with q the share of decoys among that type's files.
V, C, N_REAL = {"passwords": 10, "customer records": 6, "bank details": 8}, 20, 2


def gain(value: float, decoys: int) -> float:
    q = decoys / (decoys + N_REAL)
    return (1 - q) * value - q * C


class Drawing:
    def __init__(self, t: dict, width: int, height: int, label: str):
        self.t, self.w, self.h, self.label, self.parts = t, width, height, label, []

    # basic marks
    def text(self, x, y, s, size=12, weight=400, color="ink", anchor="start"):
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{self.t[color]}" '
                          f'text-anchor="{anchor}">{html.escape(s)}</text>')

    def rect(self, x, y, w, h, stroke="ink2", width=1.5, fill="surface", rx=10, dash=None, opacity=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        o = f' fill-opacity="{opacity}"' if opacity is not None else ""
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{self.t[fill] if fill != "none" else "none"}"{o} '
                          f'stroke="{self.t[stroke]}" stroke-width="{width}"{d}/>')

    def arrow(self, points, color="ink", width=1.8):
        pts = " ".join(f"{x},{y}" for x, y in points)
        self.parts.append(f'<polyline points="{pts}" fill="none" stroke="{self.t[color]}" stroke-width="{width}" '
                          f'stroke-linejoin="round" stroke-linecap="round" marker-end="url(#head-{color})"/>')

    def step(self, x, y, n, words, color="ink", anchor="start", size=12):
        """A step number in bold, then its words."""
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{self.t["ink"]}" text-anchor="{anchor}">'
                          f'<tspan font-weight="700" fill="{self.t[color]}">{n}</tspan>  {html.escape(words)}</text>')

    def doc(self, x, y, decoy=False, scale=1.0):
        """A file: a page with a folded corner. A decoy carries a blue dot that only the monitor sees."""
        w, h, f = 18 * scale, 23 * scale, 6 * scale
        self.parts.append(f'<path d="M{x},{y} h{w - f} l{f},{f} v{h - f} h{-w} z" fill="{self.t["surface"]}" '
                          f'stroke="{self.t["ink2"]}" stroke-width="1.4" stroke-linejoin="round"/>')
        self.parts.append(f'<path d="M{x + w - f},{y} v{f} h{f}" fill="none" stroke="{self.t["ink2"]}" stroke-width="1.2"/>')
        for i in range(2):
            yy = y + h * (0.55 + 0.2 * i)
            self.parts.append(f'<line x1="{x + 4 * scale}" y1="{yy}" x2="{x + w - 4 * scale}" y2="{yy}" stroke="{self.t["line"]}" stroke-width="1.2"/>')
        if decoy:
            self.parts.append(f'<circle cx="{x + w / 2}" cy="{y + h * 0.33}" r="{3.6 * scale}" fill="{self.t["blue"]}"/>')

    def bell(self, x, y, color="blue"):
        """An alarm bell, 16 px high, top-left corner at (x, y)."""
        self.parts.append(f'<path transform="translate({x},{y})" fill="{self.t[color]}" d="M8 1.2c-2.6 0-4.6 2-4.6 4.6v3.1'
                          f'L1.8 11.6h12.4l-1.6-2.7V5.8c0-2.6-2-4.6-4.6-4.6zM6.1 12.8a1.9 1.9 0 0 0 3.8 0z"/>')

    def bar(self, x, w, base, end, color, opacity=1.0, r=4):
        """A bar from the baseline to `end`, rounded at its far end only."""
        if abs(end - base) < 0.5:
            return
        up = end < base
        r = min(r, abs(end - base))
        if up:
            d = f"M{x},{base} V{end + r} Q{x},{end} {x + r},{end} H{x + w - r} Q{x + w},{end} {x + w},{end + r} V{base} Z"
        else:
            d = f"M{x},{base} V{end - r} Q{x},{end} {x + r},{end} H{x + w - r} Q{x + w},{end} {x + w},{end - r} V{base} Z"
        self.parts.append(f'<path d="{d}" fill="{self.t[color]}" fill-opacity="{opacity}"/>')

    def svg(self) -> str:
        heads = "".join(f'<marker id="head-{c}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="10" markerHeight="10" '
                        f'markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0,0.8 L10,5 L0,9.2 z" fill="{self.t[c]}"/></marker>'
                        for c in ("ink", "ink2", "orange", "blue"))
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" '
                f'role="img" aria-label="{html.escape(self.label)}" font-family="{FONT}">'
                f'<defs>{heads}</defs><rect width="{self.w}" height="{self.h}" fill="{self.t["surface"]}"/>'
                + "".join(self.parts) + "</svg>")


def header(d: Drawing, title: str, subtitle: str):
    d.text(24, 38, title, size=19, weight=600)
    d.text(24, 63, subtitle, size=13.5, color="ink2")


# ---------------------------------------------------------------------------------------------- 1. the hijack

def hijack(t) -> Drawing:
    d = Drawing(t, 1080, 430, "An attacker plants an email with hidden instructions. An employee asks the company's AI "
                "agent to summarize the inbox; the agent reads the email, is taken over, searches the company drive "
                "and emails the files to the attacker outside the company.")
    header(d, "How an AI agent gets hijacked",
           "Instructions hidden in something the agent reads take over, and the agent sends company secrets out.")
    d.rect(20, 86, 800, 326, stroke="line", width=1.4, fill="none", rx=14, dash="5 5")
    d.text(36, 110, "Inside the company", color="ink2")
    d.rect(840, 86, 220, 326, stroke="line", width=1.4, fill="none", rx=14, dash="5 5")
    d.text(856, 110, "Outside", color="ink2")

    d.rect(40, 212, 130, 76)                                                      # employee
    d.text(105, 246, "Employee", size=15, weight=600, anchor="middle")
    d.text(105, 267, "uses the agent", color="ink2", anchor="middle")
    d.rect(310, 200, 190, 100, stroke="ink", width=2)                             # agent
    d.text(405, 244, "AI agent", size=15, weight=600, anchor="middle")
    d.text(405, 267, "email and drive tools", color="ink2", anchor="middle")
    d.rect(412, 188, 96, 24, stroke="orange", width=1.6, rx=12)
    d.text(460, 204.5, "hijacked", size=12, weight=600, anchor="middle")
    d.rect(610, 112, 190, 104)                                                    # inbox
    d.text(626, 138, "Inbox", size=14, weight=600)
    d.text(626, 163, "Team lunch on Friday", color="ink2")
    d.rect(618, 175, 174, 30, stroke="orange", width=1.6, fill="orange", opacity=0.10, rx=6)
    d.text(630, 195, "Hidden instructions")
    d.rect(610, 284, 190, 104)                                                    # drive
    d.text(626, 310, "Company drive", size=14, weight=600)
    for i, name in enumerate(("passwords", "customer records", "bank details")):
        d.doc(627, 320 + 20 * i, scale=0.62)
        d.text(644, 333 + 20 * i, name, color="ink2")
    d.rect(864, 200, 172, 100, stroke="orange", width=2)                          # attacker
    d.text(950, 244, "Attacker", size=15, weight=600, anchor="middle")
    d.text(950, 267, "an outside address", color="ink2", anchor="middle")

    d.arrow([(950, 199), (950, 150), (803, 150)], color="orange")
    d.step(848, 140, "1", "plants an email", color="orange")
    d.arrow([(171, 250), (307, 250)], color="ink")
    d.step(240, 222, "2", "asks:", anchor="middle")
    d.text(240, 238, "“summarize my inbox”", color="ink2", anchor="middle")
    d.arrow([(609, 198), (503, 231)], color="orange")
    d.step(600, 186, "3", "reads it", color="orange", anchor="end")
    d.arrow([(501, 270), (607, 314)], color="ink")
    d.step(600, 336, "4", "searches the drive", anchor="end")
    d.arrow([(501, 250), (861, 250)], color="orange")
    d.step(705, 240, "5", "emails the files out", color="orange", anchor="middle")
    return d


# ---------------------------------------------------------------------------------------------- 2. the decoys

def decoys(t) -> Drawing:
    d = Drawing(t, 1080, 560, "Two real password files and two decoys that look alike. An honest agent opens the file it "
                "was asked for: no alarm. A naive hijacked agent sends every file: the alarm fires, but the real files "
                "leave too. A decoy-aware hijacked agent sends one file: if it is a decoy the alarm fires and nothing "
                "real is lost; if it is real, the theft is missed.")
    header(d, "How decoys catch a hijacked agent",
           "Decoys look like the real files. Only the monitor knows which ones are fake, and it raises the alarm when one leaves the company.")
    d.rect(24, 88, 1032, 78, stroke="line", width=1.4, fill="faint", rx=12)
    d.text(44, 120, "Password files on the drive", size=14, weight=600)
    d.text(44, 142, "To the agent, all four look alike.", color="ink2")
    for i, (x, kind) in enumerate(zip((392, 452, 512, 572), ("real", "real", "decoy", "decoy"))):
        d.doc(x, 100, decoy=kind == "decoy", scale=1.15)
        d.text(x + 10, 154, kind, color="ink2", anchor="middle")
    d.text(660, 120, "Each decoy holds its own fake value, which no real work uses.", color="ink2")
    d.text(660, 142, "The monitor watches every tool call for those values.", color="ink2")

    d.text(24, 204, "AGENT", size=11, weight=600, color="muted")
    d.text(426, 204, "SENDS", size=11, weight=600, color="muted")
    d.text(760, 204, "RESULT (ALARM: A DECOY SENT OUTSIDE)", size=11, weight=600, color="muted")

    def envelope(y, kinds):
        w = 30 + 28 * len(kinds) - 10
        x0 = 426
        d.rect(x0, y, w, 44, rx=8, stroke="ink2", width=1.4)
        for i, k in enumerate(kinds):
            d.doc(x0 + 15 + 28 * i, y + 10, decoy=k == "decoy", scale=0.95)
        return x0 + w

    def result(y, alarm, line1, line2=None):
        if alarm:
            d.bell(760, y - 15)
            d.text(782, y, "Alarm", size=14, weight=600)
        else:
            d.text(760, y, "No alarm", size=14, weight=600)
        d.text(760, y + 20, line1, color="ink2")
        if line2:
            d.text(760, y + 37, line2, color="ink2")

    y = 222                                                                     # honest agent
    d.text(24, y + 22, "Honest agent", size=14, weight=600)
    d.text(24, y + 42, "opens the file it was asked for", color="ink2")
    d.text(24, y + 64, "If a request only describes the file, the search can turn", color="muted")
    d.text(24, y + 81, "up decoys too, and the agent may be confused: the cost.", color="muted")
    end = envelope(y, ["real"])
    d.arrow([(end + 2, y + 22), (744, y + 22)], color="ink2")
    d.text((end + 744) / 2, y + 13, "to a colleague", color="ink2", anchor="middle")
    result(y + 22, False, "the file stays inside")

    y = 330                                                                     # naive thief
    d.text(24, y + 22, "Hijacked agent, naive", size=14, weight=600)
    d.text(24, y + 42, "sends every matching file at once", color="ink2")
    end = envelope(y, ["real", "real", "decoy", "decoy"])
    d.arrow([(end + 2, y + 22), (744, y + 22)], color="orange")
    d.text((end + 744) / 2, y + 13, "to the attacker", color="ink2", anchor="middle")
    result(y + 22, True, "but the real files left too:", "detected, not prevented")

    y = 428                                                                     # decoy-aware thief
    d.text(24, y + 22, "Hijacked agent, decoy-aware", size=14, weight=600)
    d.text(24, y + 42, "sends the one file that looks most real", color="ink2")
    for dy, kind, label, alarm, words in ((0, "decoy", "picks a decoy", True, "nothing real lost: caught"),
                                          (62, "real", "picks a real file", False, "the real file is gone: missed")):
        d.text(412, y + dy + 27, label, color="ink2", anchor="end")
        end = envelope(y + dy, [kind])
        d.arrow([(end + 2, y + dy + 22), (744, y + dy + 22)], color="orange")
        d.text((end + 744) / 2, y + dy + 13, "to the attacker", color="ink2", anchor="middle")
        result(y + dy + 22, alarm, words)
    return d


# ---------------------------------------------------------------------------------------------- 3. the game

def game(t) -> Drawing:
    d = Drawing(t, 1080, 600, "The company commits to a decoy placement; the thief learns it and steals where stealing "
                "pays most, or stays away. With the same 3 decoys all on passwords, stealing bank details still pays 8, "
                "so the thief takes them. With one decoy in each type, no type pays, so the thief stays away.")
    header(d, "The decoy game",
           "The company commits to a placement first. The thief learns it, then steals where stealing pays most, or stays away.")
    boxes = [(24, "blue", "1", "The company", ("chooses how many decoys go in each type", "of file. Each protected type costs some",
                                               "honest work, which decoys can confuse.")),
             (380, "orange", "2", "The thief", ("learns the placement, but not", "which files are the decoys.")),
             (736, "orange", "3", "The thief", ("steals from the type that pays", "most, or does not attack."))]
    for x, color, n, who, lines in boxes:
        d.rect(x, 88, 320, 100, stroke=color, width=2)
        d.step(x + 18, 116, n, who, color=color, size=14)
        for i, line in enumerate(lines):
            d.text(x + 18, 139 + 18 * i, line, color="ink2")
    d.arrow([(346, 138), (377, 138)], color="ink2")
    d.arrow([(702, 138), (733, 138)], color="ink2")

    d.text(24, 230, "The same 3 decoys, placed two ways, against a thief who sends one file", size=14, weight=600)
    base, scale = 396, 7                                                      # zero line, pixels per unit of gain
    panels = [(24, "All 3 on passwords", {"passwords": 3, "customer records": 0, "bank details": 0}),
              (548, "One in each type", {"passwords": 1, "customer records": 1, "bank details": 1})]
    for x0, name, placement in panels:
        d.rect(x0, 244, 508, 290, stroke="line", width=1.4, fill="none", rx=12)
        d.text(x0 + 18, 270, name, size=13.5, weight=600)
        d.text(x0 + 18, 290, "thief's gain from each type of file", color="ink2")
        gains = {k: gain(V[k], n) for k, n in placement.items()}
        best = max(gains, key=gains.get)
        d.parts.append(f'<line x1="{x0 + 40}" y1="{base}" x2="{x0 + 468}" y2="{base}" stroke="{t["muted"]}" stroke-width="1.2"/>')
        for i, (kind, g) in enumerate(gains.items()):
            cx = x0 + 120 + 134 * i
            pays = g > 1e-9
            d.bar(cx - 28, 56, base, base - g * scale, "orange" if pays else "muted", opacity=1.0 if pays else 0.45)
            label = "0" if abs(g) < 1e-9 else f"{g:+.1f}".replace("-", "−").replace(".0", "")
            ly = base - g * scale - 8 if g >= 0 else base - g * scale + 18
            if abs(g) < 1e-9:
                ly = base - 8
            d.text(cx, ly, label, size=13, weight=600, anchor="middle")
            if pays and kind == best:
                d.text(cx, ly - 20, "thief's pick", size=12, weight=600, color="ink", anchor="middle")
            d.text(cx, 498, kind, color="ink2", anchor="middle")
            n = placement[kind]
            if n:
                for j in range(n):
                    d.rect(cx - (n * 12 - 4) / 2 + 12 * j, 510, 8, 8, stroke="blue", width=0, fill="blue", rx=1.5)
            else:
                d.text(cx, 519, "no decoys", size=11, color="muted", anchor="middle")
        if all(g <= 1e-9 for g in gains.values()):
            d.text(x0 + 490, 270, "nothing pays: the thief stays away", size=12.5, weight=600, anchor="end")
        else:
            d.text(x0 + 490, 270, f"the thief takes the {best}", size=12.5, weight=600, anchor="end")
    d.text(24, 562, "Thief's gain from a type = (1 − q)·V − q·C, where q is the share of decoys among that type's files "
           "(each type has 2 real files),", color="ink2")
    d.text(24, 581, "V what a file is worth to the thief (passwords 10, customer records 6, bank details 8) and C the cost of "
           "being caught (20). Zero at q* = V / (V + C).", color="ink2")
    return d


# ---------------------------------------------------------------------------------------------- main

def main():
    drawings = {"hijack": hijack, "decoys": decoys, "game": game}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None
    if sync_playwright is None:
        for name, make in drawings.items():
            for theme, t in THEMES.items():
                path = os.path.join(HERE, f"{name}_{theme}.svg")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(make(t).svg())
                print("saved", os.path.relpath(path, os.path.dirname(HERE)), "(Playwright not installed, so SVG only)")
        return
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(device_scale_factor=2)
        for name, make in drawings.items():
            for theme, t in THEMES.items():
                d = make(t)
                page.set_viewport_size({"width": d.w, "height": d.h})
                page.set_content(f'<html><body style="margin:0;background:{t["surface"]}">{d.svg()}</body></html>')
                page.wait_for_timeout(100)
                path = os.path.join(HERE, f"{name}_{theme}.png")
                page.locator("svg").screenshot(path=path)
                print("saved", os.path.relpath(path, os.path.dirname(HERE)))
        browser.close()


if __name__ == "__main__":
    main()
