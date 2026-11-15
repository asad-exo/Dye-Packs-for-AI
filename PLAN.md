# Dye Packs for AI: Project Plan

Game-theoretic decoys that catch hijacked AI agents.
Asad Shahab Shafqat · ECE-GY 6263 Game Theory (Prof. Quanyan Zhu) · NYU Tandon

This file is the project's memory. Claude does not remember earlier chats, so share this file (or the repo) at the start of any new session.

## Fixed constraints

- Final presentation: Dec 4, 2026
- Final report: 6 pages, IEEE format, due Dec 19, 2026 (the course materials also list Dec 18; confirm)
- Everything else below is ordered by dependency, not by date.

## Where things stand

- Proposal submitted and approved (Option 1, the decoy project). Proposal video recorded.
- Pilot done: 106 agent runs in AgentDojo's workspace environment, about $0.75.
  - 0 of 40 false alarms with the "opened, used or leaked" alarm rule; 9 of 40 with "any sighting".
  - 37 of 40 normal tasks still completed with decoys present (no-decoy baseline not yet run).
  - Claude Haiku 5.5 and Haiku 4.5 resisted all 48 standard injection attacks.
  - 2 of 2 password hunts caught; 3 narrow one-step attacks went through uncaught.
- Pilot code and results are organized in this repo layout (see README.md); the decoy kit itself is not yet split out.

## Decisions already made

- Honest agent: a real LLM. Attackers: scripted types, because current Claude models are hard to hijack. Real hijacks on weaker models come later.
- Alarm fires on open, use or leak, not on a decoy merely appearing in a listing.
- Narrow attacks that never touch a decoy are reported as the method's limit. Decoys complement blocking.
- Running example throughout: the password hunt.
- All code, scripts and results live in the user's GitHub repo. The API key never goes in the repo.

## Prof. Zhu's feedback on the proposal (must be reflected)

1. Put the false-alarm cost explicitly in the defender's payoff; show detection vs. false alarms as an ROC-style curve per decoy policy.
2. Consider a Bayesian Stackelberg model with attacker types (naive vs. decoy-aware).
3. Include an adaptive attacker that is told decoys may exist; compare equilibrium placement with random and fixed baselines.
4. References to add: Pawlick, Colbert & Zhu (ACM Computing Surveys 2019); Píbil et al. (GameSec 2012); Paruchuri et al. (AAMAS 2008); Greshake et al. (AISec 2023).

## Setup (blocks everything else)

- [ ] Asad: create a private GitHub repo and connect GitHub to Claude; give Claude the `owner/repo` name
- [ ] Claude: push the pilot code and results; reorganize into the layout below
- [ ] Asad: confirm the API key still has credit (or create a new one)
- [ ] Asad: email Prof. Zhu the questions listed at the end of this file

Repo layout: `decoykit/` (decoys, planter, monitor, alarm rules) · `attackers/` · `model/` · `experiments/` · `results/` · `figures/` · `paper/` · `README.md` · `PLAN.md`

## Part A: Course version (must be done for Dec 4 and Dec 19)

**Must-haves**
- [ ] Claude: write up the simple model with the false-alarm cost (q* and the defender's payoff). Asad: learn it well enough to derive it unaided
- [ ] Claude: turn the pilot code into the decoy kit with pluggable placement policies (none, fixed, random, game-theoretic)
- [ ] Claude: build scripted attackers: naive (grab everything), targeted, decoy-aware
- [ ] Claude: run the no-decoy baseline on the 40 normal tasks (to see whether decoys caused the 3 task failures)
- [ ] Claude: run honest tasks (false alarms) and attacker runs (catches) for each placement
- [ ] Claude: multi-asset placement solver with a false-alarm budget (linear programming)
- [ ] Claude: ROC-style chart comparing the four placements
- [ ] Asad: review every result and chart with Claude; decide the story for the talk
- [ ] Claude drafts, Asad rewrites: final slides
- [ ] Claude drafts, Asad rewrites and checks every claim: 6-page IEEE report

**Add if time allows (drop these first if short on time)**
- [ ] Bayesian attacker types in the solver (Paruchuri et al.'s method)
- [ ] Moving decoys against attackers who learn
- [ ] Validation: rerun with the solver's recommended placement and compare with its prediction
- [ ] A second AgentDojo environment (banking or Slack)

## Part B: Publishable paper (after the course)

- [ ] Literature check: thorough search for existing work on decoys or honeypots for LLM agents; adjust the claim if needed
- [ ] Theory: formal statement and proof of optimal placement under a false-alarm budget; effect of attacker types; sensitivity to V, C and the false-alarm cost
- [ ] Models: 5–6 in total. Claude (API, runs in Claude's workspace); Gemini (free tier, runs on Asad's laptop); 2–3 open models run locally with Ollama on the laptop's RTX 5060 (8 GB: models of about 7–8B parameters; larger ones need NYU's cluster)
- [ ] Screen local models on normal tasks first; keep only those that can do the work
- [ ] Real hijacks on weaker models, not only scripted attackers
- [ ] Decoy-aware attacks written by an LLM as well as scripted ones
- [ ] All four AgentDojo environments
- [ ] Repeated runs with confidence intervals
- [ ] Robustness: wrong estimates of V and C; cost to normal task success
- [ ] Full paper with a limitations section; clean, documented code release
- [ ] Prof. Zhu's review and revisions
- [ ] arXiv, then the venue he recommends
- [ ] Disclose AI assistance as the venue requires

## Questions for Prof. Zhu

1. Is this publishable, and which venue would he aim for?
2. Is the false-alarm budget plus the benign agent as a third player enough novelty, or is a stronger theoretical result needed?
3. Are scripted attacker types acceptable, or are real hijacked agents needed?
4. False-alarm cost as a payoff penalty or a budget constraint? Two attacker types, or realism modelled as signalling?
5. How should V, C and the false-alarm cost be set or estimated?
6. Is one benchmark enough? Which baselines beyond random and fixed?
7. Any related work on deception for LLM agents to cite or differentiate from?
8. Would he advise or co-author? Could he sponsor an NYU HPC account?
9. His policy on AI assistance for the course report and for a paper.

## How Asad and Claude work together

- Claude writes code, runs experiments, drafts text and charts.
- Asad owns the ideas and decisions, checks every result, and must be able to explain all of it.
- Each working session: review what changed, decide the next step, tick items off this file.
