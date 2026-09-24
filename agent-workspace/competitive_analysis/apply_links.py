"""Write program links into the workbook's "Website Link" column, after checking that each one loads.

    cd agent-workspace
    python -m competitive_analysis.apply_links in.xlsx links_1.json links_2.json ... [--dry-run]

Link files hold [{"sheet", "row", "url", "confidence", "program_on_page", "note"}, ...] (row = Excel row).
Only blank "Website Link" cells are filled: a discovered link (confidence high/medium) wins, otherwise the
seed from colleges.py. Low-confidence and unreachable links are not written; they are listed in the log.
in.xlsx is backed up to in_before_links.xlsx (once), then updated in place; each cell gets a comment
recording where the link came from. Everything is logged to in_logs/apply_links.log.
"""
import argparse
import json
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import requests
from openpyxl import load_workbook
from openpyxl.comments import Comment

from .colleges import links_for
from .crawler import HEADERS
from .excel_io import website_column, load_frames

log = logging.getLogger("competitive_analysis.apply_links")
BLOCKED = (401, 403, 429, 999)  # the site refuses scripts; it probably works in a browser


def check(url: str) -> str:
    """'ok', 'blocked' (site refuses scripts) or a short failure reason."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=25)
    except requests.RequestException as exc:
        return type(exc).__name__
    if resp.status_code == 200:
        return "ok" if "html" in resp.headers.get("content-type", "") else f"not html ({resp.headers.get('content-type')})"
    return "blocked" if resp.status_code in BLOCKED else f"HTTP {resp.status_code}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("xlsx")
    ap.add_argument("links", nargs="*", help="discovered-link JSON files")
    ap.add_argument("--dry-run", action="store_true", help="report only; do not touch the workbook")
    args = ap.parse_args()

    src = Path(args.xlsx)
    log_dir = src.with_name(f"{src.stem}_logs")
    log_dir.mkdir(exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for handler in (logging.FileHandler(log_dir / "apply_links.log", encoding="utf-8"), logging.StreamHandler()):
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S"))
        root.addHandler(handler)

    found = {}
    for path in args.links:
        for item in json.loads(Path(path).read_text()):
            found[(item["sheet"], item["row"])] = item

    frames = load_frames(str(src))
    candidates = []  # (sheet, row, college, program, url, source, comment)
    for sheet, df in frames.items():
        col = website_column(df)
        if col is None or df.empty:
            continue
        for i in df.index:
            if str(df.iloc[i, 0]) == "nan" or str(df.iloc[i, col]) != "nan":
                continue  # blank name, or a link is already there: never overwrite
            college, program = str(df.iloc[i, 0]).strip(), "" if str(df.iloc[i, 2]) == "nan" else str(df.iloc[i, 2]).strip()
            item = found.get((sheet, i + 2))
            if item and item.get("url") and item.get("confidence") in ("high", "medium"):
                note = (f"discovered by web research ({item['confidence']} confidence); page titled "
                        f"{item.get('program_on_page')!r}. {item.get('note') or ''}").strip()
                candidates.append((sheet, i + 2, college, program, item["url"], "discovered", note))
            elif item and item.get("url"):
                log.info("NOT WRITTEN (low confidence) %s!%d %s / %s -> %s | %s", sheet, i + 2, college, program, item["url"], item.get("note"))
            elif links_for(sheet, college, program):
                candidates.append((sheet, i + 2, college, program, links_for(sheet, college, program)[0], "seeded",
                                   "seeded from the 2025-2026 workbook (may be out of date)"))
            else:
                log.info("NO LINK %s!%d %s / %s | %s", sheet, i + 2, college, program, item.get("note") if item else "not researched")

    with ThreadPoolExecutor(8) as pool:
        verdicts = list(pool.map(lambda c: check(c[4]), candidates))

    wb = load_workbook(src)
    written = 0
    for (sheet, row, college, program, url, source, note), verdict in zip(candidates, verdicts):
        if verdict not in ("ok", "blocked"):
            log.warning("REJECTED (%s) %s!%d %s / %s -> %s", verdict, sheet, row, college, program, url)
            continue
        log.info("WRITE %s!D%d %s / %s -> %s [%s, check: %s]", sheet, row, college, program, url, source, verdict)
        ws = wb[sheet]
        cell = ws.cell(row=row, column=website_column(frames[sheet]) + 1, value=url)
        stamp = f"{note} Checked {date.today()}: " + ("loads." if verdict == "ok" else "site blocks scripts, not verified.")
        cell.comment = Comment(stamp, "competitive-analysis-agent", width=420, height=120)
        written += 1
    if written and not args.dry_run:
        backup = src.with_name(f"{src.stem}_before_links{src.suffix}")
        if not backup.exists():
            shutil.copy2(src, backup)
            log.info("Backed up original -> %s", backup)
        wb.save(src)
    log.info("DONE: %d link(s) %s in %s; %d candidate(s) rejected", written, "would be written" if args.dry_run else "written",
             src, len(candidates) - written)


if __name__ == "__main__":
    main()
