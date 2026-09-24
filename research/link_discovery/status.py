"""Show which rows of remaining_N.json still lack a finding in findings/remaining_N.jsonl."""
import json
from pathlib import Path

here = Path(__file__).parent
for n in (1, 2, 3, 4):
    todo = json.loads((here / f"remaining_{n}.json").read_text())
    f = here / "findings" / f"remaining_{n}.jsonl"
    seen = {(d["sheet"], d["row"]) for d in map(json.loads, f.read_text().splitlines() if f.exists() else [])}
    left = [t for t in todo if (t["sheet"], t["row"]) not in seen]
    print(f"remaining_{n}: {len(todo) - len(left)}/{len(todo)} done; left: {[(t['sheet'], t['row']) for t in left]}")
