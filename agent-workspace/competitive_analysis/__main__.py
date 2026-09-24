"""Fill a competitive-analysis Excel workbook from college websites.

    cd agent-workspace
    python -m competitive_analysis in.xlsx --cycle "2026-2027 academic year" [--sheet "Online MSGSCM"] [--limit 3]

Per program sheet, every college row is researched for the fields to the right of "Website Link", using the
program name in column C (falling back to the sheet name) as the target program. Writes in_filled.xlsx (or
overwrites in.xlsx with --inplace) and, in in_logs/:
  run.log         every fetch, link, queue decision, LLM finding, rejection, decision and cell change
  llm.jsonl       every prompt sent to RCAC and the raw reply
  pages/          full text of every fetched page
  report.json     per-field status, source URL, quote and all candidates (also the resume checkpoint)
Only verified values go into the sheet, each with a cell comment holding its source URL and quote.

Needs RCAC_API_KEY (env or .env) and starting links in colleges.py.
"""
import argparse
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from openpyxl.utils import get_column_letter

from . import crawler, rcac
from .agent import FILLED, Context, research_college
from .colleges import links_for
from .excel_io import classify_columns, is_blank, load_frames, paired_field, website_column, write_back

log = logging.getLogger("competitive_analysis")


def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")
    for handler in (logging.FileHandler(log_dir / "run.log", mode="a", encoding="utf-8"), logging.StreamHandler()):
        handler.setLevel(logging.DEBUG if isinstance(handler, logging.FileHandler) else logging.INFO)
        handler.setFormatter(fmt)
        root.addHandler(handler)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    crawler.PAGE_DIR = log_dir / "pages"
    rcac.LLM_LOG = log_dir / "llm.jsonl"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("xlsx")
    ap.add_argument("--cycle", required=True, help='cycle to look for, e.g. "2026-2027 academic year" or "Fall 2027"')
    ap.add_argument("--as-of", default=date.today().isoformat(), help="today's date (YYYY-MM-DD); default: system date")
    ap.add_argument("--sheet", action="append", help="only this sheet (exact name; repeatable)")
    ap.add_argument("--limit", type=int, help="stop after researching this many colleges (for pilots)")
    ap.add_argument("--inplace", action="store_true", help="overwrite the input file instead of writing *_filled.xlsx")
    ap.add_argument("--overwrite", action="store_true", help="re-research cells that already have a value")
    ap.add_argument("--max-pages", type=int, default=30, help="pages fetched per college")
    ap.add_argument("--max-depth", type=int, default=4, help="link depth from the starting links")
    ap.add_argument("--workers", type=int, default=6, help="colleges (different sites) researched concurrently")
    args = ap.parse_args()

    src = Path(args.xlsx)
    log_dir = src.with_name(f"{src.stem}_logs")
    setup_logging(log_dir)
    dest = src if args.inplace else src.with_name(f"{src.stem}_filled{src.suffix}")
    today = date.fromisoformat(args.as_of)
    log.info("##### RUN START %s | input %s | output %s | cycle %r | today %s | sheets %s | limit %s | max pages %d, depth %d, %d workers",
             date.today(), src, dest, args.cycle, today, args.sheet or "all", args.limit, args.max_pages, args.max_depth, args.workers)

    report_path = log_dir / "report.json"
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    if report.get("context", {}).get("cycle") != args.cycle:
        if report:
            log.warning("Report was made for cycle %r; starting fresh for %r", report["context"].get("cycle"), args.cycle)
        report = {"context": {"cycle": args.cycle, "started": today.isoformat()}, "colleges": {}}

    frames = load_frames(str(src))
    changed: dict[str, list[tuple[int, str, str]]] = {}
    unlinked: list[str] = []
    researched = 0
    io_lock = threading.Lock()  # guards frame mutation, report.json and the workbook file (all single-writer)

    def set_cell(sheet: str, row: int, col: str, value, note: str) -> None:
        df = frames[sheet]
        cell = f"{get_column_letter(list(df.columns).index(col) + 1)}{row + 2}"
        log.info("CELL %s!%s | %s | %r -> %r | %s", sheet, cell, col, None if is_blank(df.at[row, col]) else df.at[row, col],
                 value, note.replace("\n", " | "))
        df.at[row, col] = value
        changed.setdefault(sheet, []).append((row, col, note))

    def apply_result(sheet, row, college, ctx, fields, link_cols, wanted, wanted_links, entry) -> None:
        """Write an entry's researched fields into the sheet and save. Runs on the single consumer thread."""
        for field in wanted:
            found = entry["fields"].get(field)
            if found and found["status"] in FILLED:
                set_cell(sheet, row, field, found["value"],
                         f'{found["status"]} | {ctx.cycle} | {ctx.program}\n{found["source"]}\n"{found["quote"]}"')
            else:
                log.info("LEFT BLANK %s!%d %r: %s", sheet, row + 2, field, found["status"] if found else "not researched")
        for col in wanted_links:
            pair = paired_field(col, fields)
            found = entry["fields"].get(pair) if pair else None
            if found and found["status"] in FILLED:
                set_cell(sheet, row, col, found["source"], f"page where '{pair}' was found ({found['status']})")
            else:
                log.info("LEFT BLANK %s!%d %r: no verified value for its paired field %r", sheet, row + 2, col, pair)
        write_back(str(src), str(dest), frames, changed)  # progress is on disk after every college
        log.info("Saved workbook -> %s (%d cells written so far)", dest, sum(map(len, changed.values())))

    # Phase 1: walk sheets/rows exactly as before, building one research job per college that needs it.
    # Cheap, single-threaded; no network calls happen here, so frame/report mutation needs no lock yet.
    jobs = []  # (sheet, row, college, ctx, urls, todo, fields, link_cols, wanted, wanted_links, entry)
    for sheet, df in frames.items():
        if args.sheet and sheet not in args.sheet:
            log.info("SKIP sheet %r (not selected)", sheet)
            continue
        web = website_column(df)
        if web is None or df.empty:
            log.info("SKIP sheet %r (not a program sheet with rows)", sheet)
            continue
        fields, link_cols, skipped = classify_columns(df)
        log.info("SHEET %r: %d rows | %d fields to research | %d link columns | %d skipped columns",
                 sheet, len(df), len(fields), len(link_cols), len(skipped))
        for col, why in skipped.items():
            log.info("  SKIP column %r: %s", col, why)
        for col in link_cols:
            log.info("  LINK column %r <- source URL of %r", col, paired_field(col, fields))
        web_col = df.columns[web]

        for row in df.index:
            if args.limit is not None and len(jobs) >= args.limit:
                break
            if is_blank(df.iloc[row, 0]):
                continue
            college = str(df.iloc[row, 0]).strip()
            program_name = "" if is_blank(df.iloc[row, 2]) else str(df.iloc[row, 2]).strip()
            ctx = Context(today, args.cycle, f"{program_name or '(program name not given)'} - listed on the workbook sheet '{sheet}'")
            wanted = [f for f in fields if args.overwrite or is_blank(df.at[row, f])]
            wanted_links = [c for c in link_cols if args.overwrite or is_blank(df.at[row, c])]
            if not wanted and not wanted_links:
                log.info("ROW %s!%d %s: nothing blank to fill", sheet, row + 2, college)
                continue
            # The workbook's own "Website Link" is the source of truth; colleges.py is the fallback seed.
            urls = [str(df.at[row, web_col]).strip()] if not is_blank(df.at[row, web_col]) else links_for(sheet, college, program_name)
            if not urls:
                log.warning("NO LINK for %s!%d %s / %s -> skipped (fill the Website Link cell or add it to colleges.py)", sheet, row + 2, college, program_name or "-")
                unlinked.append(f"{sheet}: {college} / {program_name or '-'}")
                continue
            log.info("START LINK %s!%d %s / %s -> %s", sheet, row + 2, college, program_name or "-", urls)
            if is_blank(df.at[row, web_col]):
                set_cell(sheet, row, web_col, urls[0], "starting link seeded from the 2025-2026 workbook (colleges.py)")

            key = f"{sheet}::{college}::{program_name}"
            entry = report["colleges"].get(key)
            if entry is None or entry.get("program") != ctx.program:
                entry = report["colleges"][key] = {"program": ctx.program, "fields": {}}
            todo = wanted if args.overwrite else [f for f in wanted if f not in entry["fields"]]
            if todo:
                jobs.append((sheet, row, college, ctx, urls, todo, fields, link_cols, wanted, wanted_links, entry))
            else:
                log.info("Resuming %s from report.json (all fields already researched)", college)
                apply_result(sheet, row, college, ctx, fields, link_cols, wanted, wanted_links, entry)

    # Phase 2: research jobs concurrently (each on its own site), applying results one at a time as they land.
    log.info("Researching %d college(s) with %d concurrent worker(s)", len(jobs), args.workers)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {}
        for job in jobs:
            _, _, college, ctx, urls, todo, *_ = job
            futures[pool.submit(research_college, college, urls, todo, ctx, args.max_pages, args.max_depth)] = job
        for future in as_completed(futures):
            sheet, row, college, ctx, urls, todo, fields, link_cols, wanted, wanted_links, entry = futures[future]
            results, pages = future.result()
            with io_lock:
                researched += 1
                entry["fields"].update(results)
                entry["pages"] = pages
                report_path.write_text(json.dumps(report, indent=2))
                apply_result(sheet, row, college, ctx, fields, link_cols, wanted, wanted_links, entry)

    write_back(str(src), str(dest), frames, changed)
    filled = sum(map(len, changed.values()))
    review = sum(1 for e in report["colleges"].values() for f in e["fields"].values() if f["status"] not in FILLED)
    log.info("##### RUN END: %d colleges researched, %d cells written -> %s; %d field(s) left blank for review; %d row(s) without links",
             researched, filled, dest, review, len(unlinked))
    for item in unlinked:
        log.info("  no link: %s", item)
    print(f"\nWrote {filled} cells -> {dest}\nLogs, pages and report -> {log_dir}\n"
          f"{review} researched field(s) left blank; {len(unlinked)} row(s) skipped for lack of a link (listed in run.log)")


if __name__ == "__main__":
    main()
