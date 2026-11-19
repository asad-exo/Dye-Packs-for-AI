# decoykit

The decoy kit for AgentDojo's workspace environment.

| File | What it does |
|---|---|
| `assets.py` | The asset classes (credentials, customer records, bank details): the real items planted so there is something to steal, and decoy templates at three realism levels |
| `placement.py` | Placement policies (none, fixed, random, explicit counts from the solver) and `plant()`, which writes real items and decoys into the drive |
| `monitor.py` | `MonitoredRuntime`, which records every time a planted item is listed, searched, opened, used or leaked, plus the alarm rules and per-run outcomes |

```python
import random
from agentdojo.task_suite.load_suites import get_suite
from decoykit import MonitoredRuntime, fixed_policy, outcome, plant, tools_for

suite = get_suite("v1.2.2", "workspace")
env = suite.load_and_inject_default_environment({})
placement = fixed_policy(per_class=2, realism="high")
registry = plant(env, placement, random.Random(0))
runtime = MonitoredRuntime(tools_for(suite, placement), registry)
# ... let an agent (or a scripted attacker) act through `runtime` ...
print(outcome(runtime.events, rule="act"))
```
