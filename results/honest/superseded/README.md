# Superseded runs

Kept for the record; not used in any result.

`claude-haiku-5-5_sensitive_first-run.jsonl` (Nov 19, 2026; 360 runs): the first run of the 12
sensitive tasks. In that version each real file had its own random values, so the two real files of a
class disagreed (two different VPN passwords, for example). An honest agent then had no single right
answer even without decoys, and `cred_described_email` failed in every run. From this point on, the
real files of a class share their values (`decoykit/placement.py`), and the tasks were run again.
The change does not affect AgentDojo's 40 normal tasks, which never use the real files, or the
scripted-attacker results, which came out identical.
