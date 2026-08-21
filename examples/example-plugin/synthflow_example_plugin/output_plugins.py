"""Example SynthFlow output plugin.

Demonstrates the contract every entry under the "synthflow.outputs"
entry-point group must follow: a callable — sync or async — taking
(config: dict, rows: list[dict]) that delivers one batch of freshly
generated rows somewhere. SynthFlow's generic background loop
(app/services/plugin_output_producers.py in the main repo) owns pacing
(events_per_second) and batch loading; this function only owns delivery.
This one is intentionally sync, to demonstrate that a plugin author
doesn't have to know asyncio to write one — SynthFlow runs a sync
delivery function in a thread so it can't block the event loop.
"""

import json


def write_jsonl(config: dict, rows: list[dict]) -> None:
    path = config["path"]
    with open(path, "a") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
