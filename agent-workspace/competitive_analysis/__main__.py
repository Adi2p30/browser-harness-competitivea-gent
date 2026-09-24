"""Fill a competitive-analysis Excel workbook from college websites.

    cd agent-workspace
    python -m competitive_analysis in.xlsx --online --fetch browser [--sheet "Online MSGSCM"] [--limit 3]

Per program sheet, every college row is researched for the fields to the right of "Website Link", using the
program name in column C (falling back to the sheet name) as the target program. Writes in_filled.xlsx (or
overwrites in.xlsx with --inplace) and, in in_logs/:
  run.log         every fetch, link, queue decision, LLM finding, rejection, decision and cell change
  llm.jsonl       every prompt sent to RCAC / Claude and the raw reply
  pages/          full text of every fetched page
  report.json     per-field status, source URL, quote and all candidates (also the resume checkpoint)
Models: RCAC first, then Claude Opus 5.5 for every field RCAC could not fill (or for everything if RCAC is down);
each chosen value is re-checked by the same model that found it. Only the target cycle (default 2026-2027) is
accepted; quotes naming another year are rejected in code. Every cell of a researched row is filled: the verified
value, or a marked "UNVERIFIED: ..." / "Not found (2026-27)" / "Not published by school" placeholder, each with a
cell comment (source URL + quote, or the pages checked). Field definitions come from
agent-workspace/domain-skills/competitive-analysis/*.md.

Needs RCAC_API_KEY and/or ANTHROPIC_API_KEY (env or .env).
"""
import argparse
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from openpyxl.utils import get_column_letter

from . import claude, crawler, rcac
from .agent import FILLED, Context, best_effort, research_college
from .colleges import links_for, no_online_program
from .excel_io import classify_columns, is_blank, load_frames, paired_field, website_column, write_back

log = logging.getLogger("competitive_analysis")
DEFAULT_CYCLE = "2026-2027 academic year (Fall 2026, Spring 2027 and Summer 2027 terms)"
NOT_FOUND = "Not found (2026-27)"
NOT_PUBLISHED = "Not published by school"
NO_LINK = "No program link found"
NO_PROGRAM = "No online program offered"
PLACEHOLDERS = (NOT_FOUND, NOT_PUBLISHED, NO_LINK, NO_PROGRAM, "UNVERIFIED:")
SCHOOL_COLUMN = "School / College Name"


def needs_value(value) -> bool:
    """Blank, or something this tool wrote as a stand-in (re-researched on the next run)."""
    return is_blank(value) or str(value).startswith(PLACEHOLDERS)


def is_note_row(name: str) -> bool:
    return "not ranked" in name.casefold()


def pick_models(requested: list[str]) -> list[str]:
    usable = []
    for m in requested:
        ok = rcac.available() if m == "rcac" else claude.available() if m == "claude" else False
        log.info("MODEL %s: %s", m, "available" if ok else "NOT available (no API key) -> skipped")
        if ok:
            usable.append(m)
    return usable


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
    rcac.LLM_LOG = claude.LLM_LOG = log_dir / "llm.jsonl"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("xlsx")
    ap.add_argument("--cycle", default=DEFAULT_CYCLE, help=f'cycle to look for (default: "{DEFAULT_CYCLE}")')
    ap.add_argument("--as-of", default=date.today().isoformat(), help="today's date (YYYY-MM-DD); default: system date")
    ap.add_argument("--sheet", action="append", help="only this sheet (exact name; repeatable)")
    ap.add_argument("--online", action="store_true", help='only sheets whose name starts with "Online"')
    ap.add_argument("--models", default="rcac,claude", help="models in the order they are tried (default: rcac,claude)")
    ap.add_argument("--fetch", choices=("browser", "auto", "requests"), default="browser",
                    help="browser: render every page with browser-harness (plain HTTP fallback); auto: plain HTTP, "
                         "browser only for pages it cannot read; requests: never the browser (default: browser)")
    ap.add_argument("--no-verify", dest="verify", action="store_false", help="skip the same-model verification pass")
    ap.add_argument("--retry-unfilled", action="store_true",
                    help="re-research fields report.json holds as not found/unverified (default: reuse them)")
    ap.add_argument("--leave-blank", action="store_true", help="leave unverified cells blank instead of filling them")
    ap.add_argument("--limit", type=int, help="stop after researching this many colleges (for pilots)")
    ap.add_argument("--inplace", action="store_true", help="overwrite the input file instead of writing *_filled.xlsx")
    ap.add_argument("--overwrite", action="store_true", help="re-research cells that already have a value")
    ap.add_argument("--max-pages", type=int, default=40, help="pages read per college per model")
    ap.add_argument("--max-depth", type=int, default=4, help="link depth from the starting links")
    ap.add_argument("--workers", type=int, default=6, help="colleges (different sites) researched concurrently")
    args = ap.parse_args()

    src = Path(args.xlsx)
    log_dir = src.with_name(f"{src.stem}_logs")
    setup_logging(log_dir)
    dest = src if args.inplace else src.with_name(f"{src.stem}_filled{src.suffix}")
    today = date.fromisoformat(args.as_of)
    crawler.BROWSER_FIRST = args.fetch == "browser"
    crawler.USE_BROWSER = crawler.USE_BROWSER or args.fetch == "auto"
    models = pick_models([m.strip() for m in args.models.split(",") if m.strip()])
    if not models:
        raise SystemExit("No usable model: set RCAC_API_KEY and/or ANTHROPIC_API_KEY (env or .env)")
    log.info("##### RUN START %s | input %s | output %s | cycle %r | today %s | sheets %s | limit %s | max pages %d, depth %d, "
             "%d workers | models %s | verify %s | fetch %s", date.today(), src, dest, args.cycle, today,
             args.sheet or ("Online*" if args.online else "all"), args.limit, args.max_pages, args.max_depth,
             args.workers, models, args.verify, args.fetch)

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
        checked = ", ".join(entry.get("pages", {}).get("visited", [])[:15]) or "none"
        for field in wanted:
            found = entry["fields"].get(field)
            if found and found["status"] in FILLED:
                by = f' | verified by {found["verified_by"]}' if found.get("verified_by") else ""
                set_cell(sheet, row, field, found["value"], f'{found["status"]}{by} | {found.get("model", "rcac")} | '
                         f'{ctx.cycle} | {ctx.program}\n{found["source"]}\n"{found["quote"]}"')
            elif args.leave_blank:
                log.info("LEFT BLANK %s!%d %r: %s", sheet, row + 2, field, found["status"] if found else "not researched")
            elif found and (guess := best_effort(found)):
                set_cell(sheet, row, field, f"UNVERIFIED: {guess[0]}", f"NOT VERIFIED - review | {guess[1]}")
            else:
                set_cell(sheet, row, field, NOT_FOUND, f'{found["status"] if found else "not researched"} for '
                         f'{ctx.cycle} | {ctx.program}\npages checked: {checked}')
        for col in wanted_links:
            pair = paired_field(col, fields)
            found = entry["fields"].get(pair) if pair else None
            if found and found["status"] in FILLED:
                set_cell(sheet, row, col, found["source"], f"page where '{pair}' was found ({found['status']})")
            elif args.leave_blank:
                log.info("LEFT BLANK %s!%d %r: no verified value for its paired field %r", sheet, row + 2, col, pair)
            else:
                set_cell(sheet, row, col, NOT_FOUND, f"no verified value for '{pair}'\npages checked: {checked}")
        write_back(str(src), str(dest), frames, changed)  # progress is on disk after every college
        log.info("Saved workbook -> %s (%d cells written so far)", dest, sum(map(len, changed.values())))

    # Phase 1: walk sheets/rows exactly as before, building one research job per college that needs it.
    # Cheap, single-threaded; no network calls happen here, so frame/report mutation needs no lock yet.
    jobs = []  # (sheet, row, college, ctx, urls, todo, fields, link_cols, wanted, wanted_links, entry)
    for sheet, df in frames.items():
        if (args.sheet and sheet not in args.sheet) or (args.online and not sheet.casefold().startswith("online")):
            log.info("SKIP sheet %r (not selected)", sheet)
            continue
        web = website_column(df)
        if web is None or df.empty:
            log.info("SKIP sheet %r (not a program sheet with rows)", sheet)
            continue
        fields, link_cols, skipped = classify_columns(df)
        if SCHOOL_COLUMN in df.columns:
            fields = [SCHOOL_COLUMN] + fields
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
            if is_note_row(college):
                log.info("ROW %s!%d is a note, not a college: %r", sheet, row + 2, college)
                continue
            program_name = "" if is_blank(df.iloc[row, 2]) else str(df.iloc[row, 2]).strip()
            ctx = Context(today, args.cycle, f"{program_name or '(program name not given)'} - listed on the workbook sheet '{sheet}'")
            wanted = [f for f in fields if args.overwrite or needs_value(df.at[row, f])]
            wanted_links = [c for c in link_cols if args.overwrite or needs_value(df.at[row, c])]
            if not args.leave_blank:
                for col in skipped:
                    if needs_value(df.at[row, col]) and not str(df.at[row, col]).startswith(NOT_PUBLISHED):
                        set_cell(sheet, row, col, NOT_PUBLISHED, f"{col}: {skipped[col]}")
            if not wanted and not wanted_links:
                log.info("ROW %s!%d %s: nothing blank to fill", sheet, row + 2, college)
                continue
            # The workbook's own "Website Link" is the source of truth; colleges.py is the fallback seed.
            own = [] if needs_value(df.at[row, web_col]) else [str(df.at[row, web_col]).strip()]
            urls = list(dict.fromkeys(own + links_for(sheet, college, program_name)))  # every known link is a start
            if not urls:
                log.warning("NO LINK for %s!%d %s / %s -> skipped (fill the Website Link cell or add it to colleges.py)", sheet, row + 2, college, program_name or "-")
                unlinked.append(f"{sheet}: {college} / {program_name or '-'}")
                if not args.leave_blank:
                    note = no_online_program(sheet, college)
                    for col in [web_col] + wanted + wanted_links:
                        set_cell(sheet, row, col, NO_PROGRAM if note else NO_LINK,
                                 note or "no Website Link in the workbook and none in colleges.py")
                continue
            log.info("START LINK %s!%d %s / %s -> %s", sheet, row + 2, college, program_name or "-", urls)
            if needs_value(df.at[row, web_col]):
                set_cell(sheet, row, web_col, urls[0], "starting link seeded from the 2025-2026 workbook (colleges.py)")

            key = f"{sheet}::{college}::{program_name}"
            entry = report["colleges"].get(key)
            if entry is None or entry.get("program") != ctx.program:
                entry = report["colleges"][key] = {"program": ctx.program, "fields": {}}
            todo = wanted if args.overwrite else [f for f in wanted if f not in entry["fields"] or (
                args.retry_unfilled and entry["fields"][f]["status"] not in FILLED)]
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
            futures[pool.submit(research_college, college, urls, todo, ctx, args.max_pages, args.max_depth,
                                tuple(models), args.verify)] = job
        for future in as_completed(futures):
            sheet, row, college, ctx, urls, todo, fields, link_cols, wanted, wanted_links, entry = futures[future]
            results, pages = future.result()
            with io_lock:
                researched += 1
                entry["fields"].update(results)
                for f in todo:  # a field the research did not return is recorded, so a resume does not loop on it
                    entry["fields"].setdefault(f, {"value": None, "status": "not-researched", "source": None,
                                                   "quote": None, "candidates": []})
                entry["pages"] = pages
                report_path.write_text(json.dumps(report, indent=2))
                apply_result(sheet, row, college, ctx, fields, link_cols, wanted, wanted_links, entry)

    write_back(str(src), str(dest), frames, changed)
    log.info("Fetch stats: %s", crawler.STATS)
    filled = sum(map(len, changed.values()))
    review = sum(1 for e in report["colleges"].values() for f in e["fields"].values() if f["status"] not in FILLED)
    log.info("##### RUN END: %d colleges researched, %d cells written -> %s; %d field(s) left blank for review; %d row(s) without links",
             researched, filled, dest, review, len(unlinked))
    for item in unlinked:
        log.info("  no link: %s", item)
    print(f"\nWrote {filled} cells -> {dest}\nLogs, pages and report -> {log_dir}\n"
          f"{review} researched field(s) {'left blank' if args.leave_blank else 'not verified (filled as UNVERIFIED / Not found)'}; "
          f"{len(unlinked)} row(s) skipped for lack of a link (listed in run.log)")


if __name__ == "__main__":
    main()
