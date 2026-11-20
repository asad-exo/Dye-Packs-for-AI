# attackers

Scripted hijacked agents, one per attacker type. Each acts only through the agent's normal tools and never sees which items are decoys.

| Attacker | Behaviour |
|---|---|
| `grab_all` | Searches for the target and sends everything that matches |
| `pick_one` | Searches for the target and sends one matching file at random |
| `decoy_aware` | Lists the drive, scores each candidate for tell-tale signs (odd file type, naming, never shared, very recent), sends the least suspicious |
| `informed` | Already knows a real file's exact name and goes straight for it |

Not built yet: an attacker that learns where fixed decoys are over repeated attacks.

## Real hijack attempts (`injections.py`)

Six attacker goals, one per kind of secret (passwords, customer records, bank details), each in two
versions: **naive** (find it and email it to the attacker) and **aware** (the same, plus a warning that
decoys exist and how to spot them, using the same tell-tale signs as `decoy_aware` above). The text is
wrapped in AgentDojo's "important instructions" attack and hidden in an email, calendar entry or file
that the agent reads during a normal task. `experiments/hijack_runs.py` runs them.

