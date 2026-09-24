"""Export every value the run filled, with the page it came from, as one CSV.

    cd agent-workspace
    BU_CDP_URL=http://127.0.0.1:9333 python -m competitive_analysis.export_csv <logs_dir> [out.csv]

Reads <logs_dir>/report.json (only verified values) and opens each distinct source URL once in a real browser via
browser-harness, so the link_check column shows whether the link actually loads (bot-blocked sites included).
"""
import csv
import json
import sys
from pathlib import Path

from . import crawler
from .agent import FILLED

COLUMNS = ["sheet", "college", "program", "field", "value", "status", "source_url", "link_check", "quote"]


def main() -> None:
    logs = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else logs / "values_with_sources.csv"
    report = json.loads((logs / "report.json").read_text())
    rows = []
    for key, entry in report["colleges"].items():
        sheet, college, _ = key.split("::", 2)
        for field, r in entry["fields"].items():
            if r["status"] in FILLED:
                rows.append({"sheet": sheet, "college": college, "program": entry["program"], "field": field,
                             "value": r["value"], "status": r["status"], "source_url": r["source"], "quote": r["quote"]})
    checks = {}
    for url in sorted({r["source_url"] for r in rows}):
        checks[url] = crawler.check_link(url)
        print(f"{checks[url]:<40} {url}", flush=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, COLUMNS)
        w.writeheader()
        w.writerows({**r, "link_check": checks[r["source_url"]]} for r in rows)
    bad = sum(not c.startswith("ok") for c in checks.values())
    print(f"\n{len(rows)} values, {len(checks)} distinct links ({bad} failed) -> {out}")


if __name__ == "__main__":
    main()
