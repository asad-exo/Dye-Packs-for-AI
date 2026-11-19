# attackers

Scripted hijacked agents, one per attacker type. Each acts only through the agent's normal tools and never sees which items are decoys.

| Attacker | Behaviour |
|---|---|
| `grab_all` | Searches for the target and sends everything that matches |
| `pick_one` | Searches for the target and sends one matching file at random |
| `decoy_aware` | Lists the drive, scores each candidate for tell-tale signs (odd file type, naming, never shared, very recent), sends the least suspicious |
| `informed` | Already knows a real file's exact name and goes straight for it |

Not built yet: an attacker that learns where fixed decoys are over repeated attacks.
