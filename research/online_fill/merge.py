"""Merge research + verification agent output into the workbook, applying the same checks as the pipeline.

    uv run --with openpyxl --with pandas --with requests --with beautifulsoup4 --with anthropic \
        python research/online_fill/merge.py

A value is written as verified only if: the field belongs to the row, its digits are in its quote, the quote names
no year/term outside 2026-2027 (code check), and the verification agent said "correct". Everything else on an
Online sheet is filled with a marked placeholder. Output: "<workbook>_online_filled.xlsx" + merge_report.json.
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent-workspace"))
from competitive_analysis.__main__ import (DEFAULT_CYCLE, NO_PROGRAM, NOT_FOUND, NOT_PUBLISHED,  # noqa: E402
                                           is_note_row, needs_value)
from competitive_analysis.agent import Context  # noqa: E402
from competitive_analysis.colleges import links_for, no_online_program  # noqa: E402
from competitive_analysis.excel_io import classify_columns, is_blank, load_frames, website_column, write_back  # noqa: E402

HERE = Path(__file__).parent
SRC = ROOT / "EDIT Competitive Analysis Research 2026-2027.xlsx"
DEST = SRC.with_name(f"{SRC.stem}_online_filled{SRC.suffix}")
# Descriptive columns hold prose answers; the digit check applies to numeric columns only.
PROSE = re.compile(r"link|description|yes/no|\(y/n\)|3yr|scholarship|delivery|on-campus|school / college|location", re.I)
CTX = Context(date(2026, 9, 24), DEFAULT_CYCLE, "online program")


def read_jsonl(pattern: str) -> dict[tuple, dict]:
    out = {}
    for path in sorted(HERE.glob(pattern)):
        for line in path.read_text().splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(d, dict) and {"sheet", "row", "field"} <= d.keys():
                out[(d["sheet"], int(d["row"]), d["field"])] = d  # last line wins
    return out


WORDS = {w: i for i, w in enumerate("one two three four five six seven eight nine ten".split(), 1)}


def code_check(f: dict, verified: bool = False) -> str | None:
    value = str(f.get("value") or "").strip()
    quote = re.sub(r"\[[^\]]*\]", " ", str(f.get("quote") or ""))  # agent-added [notes] are not page text
    if not value:
        return "empty value"
    if not PROSE.search(f["field"]):
        digits = re.sub(r"[,\s]", "", quote)
        missing = [d for d in re.findall(r"\d+", value.replace(",", "")) if d not in digits]
        # the field guide converts years to months for these columns: accept exactly 12 x a year figure in the quote
        years = {float(n) * 12 for m in re.finditer(r"(\d+(?:\.\d+)?)(?:\s*(?:-|to|\u2013)\s*(\d+(?:\.\d+)?))?\s*years?",
                                                  quote, re.I) for n in m.groups() if n}
        years |= {12.0 * n for w, n in WORDS.items()  # "one and two years", "six years", "one calendar year"
                  if re.search(rf"\b{w}\b(?=[^.]{{0,40}}?\byears?\b)", quote, re.I)}
        if re.search(r"duration|time commitment|work experience", f["field"], re.I):
            missing = [d for d in missing if float(d) not in years]
        if verified:  # the verifier independently confirmed the value for the 2026-2027 cycle
            missing = [d for d in missing if d not in ("2026", "2027")]
        if missing:
            return "value digits not in quote"
    return CTX.cycle_violation(f"{quote} {value}", "deadline" in f["field"].casefold())


def main() -> None:
    findings, verdicts = read_jsonl("findings/batch_*.jsonl"), read_jsonl("verify/batch_*.jsonl")
    # second pass (retry/): a value it found replaces the first pass's finding and verdict for that cell
    retry_verdicts, retry_misses = read_jsonl("retry/verify/batch_*.jsonl"), {}
    for key, f in read_jsonl("retry/findings/batch_*.jsonl").items():
        if f.get("status") == "found":
            findings[key], verdicts[key] = f, retry_verdicts.get(key, {})
        else:
            retry_misses[key] = f.get("quote") or ""
    frames = load_frames(str(SRC))
    changed: dict[str, list] = {}
    stats = {"verified": 0, "unverified": 0, "rejected_by_code": 0, "rejected_by_verifier": 0, "not_found": 0,
             "not_published": 0, "no_program": 0}
    rejects = []

    def put(sheet, df, row, col, value, note, link=""):
        df.at[row, col] = value
        changed.setdefault(sheet, []).append((row, col, note, link))

    for sheet, df in frames.items():
        if not sheet.startswith("Online") or df.empty or website_column(df) is None:
            continue
        fields, link_cols, skipped = classify_columns(df)
        web = df.columns[website_column(df)]
        for row in df.index:
            college = "" if is_blank(df.iloc[row, 0]) else str(df.iloc[row, 0]).strip()
            if not college or is_note_row(college):
                continue
            targets = [c for c in df.columns[1:] if not str(c).startswith("Unnamed") and c != df.columns[2]]
            if note := no_online_program(sheet, college):
                for col in targets:
                    if needs_value(df.at[row, col]):
                        put(sheet, df, row, col, NO_PROGRAM, note)
                        stats["no_program"] += 1
                continue
            if needs_value(df.at[row, web]) and (seed := links_for(sheet, college, "" if is_blank(df.iloc[row, 2])
                                                                   else str(df.iloc[row, 2]))):
                put(sheet, df, row, web, seed[0], "starting link (colleges.py, from research/link_discovery)")
            for col in targets:
                if col == web or not needs_value(df.at[row, col]):
                    continue
                if col in skipped:
                    put(sheet, df, row, col, NOT_PUBLISHED, f"{col}: {skipped[col]}")
                    stats["not_published"] += 1
                    continue
                f = findings.get((sheet, row + 2, col))
                if not f or f.get("status") != "found":
                    why = (f or {}).get("quote") or "no finding"
                    if (miss := retry_misses.get((sheet, row + 2, col))) is not None:
                        why = f"second pass: {miss} | first pass: {why}"
                    put(sheet, df, row, col, NOT_FOUND, f"not found for 2026-2027 | {why}"[:900])
                    stats["not_found"] += 1
                    continue
                v = verdicts.get((sheet, row + 2, col), {})
                if bad := code_check(f, v.get("verdict") == "correct"):
                    rejects.append({**f, "rejected": bad})
                    put(sheet, df, row, col, NOT_FOUND, f"candidate {f['value']!r} rejected by code check: {bad}\n"
                                                        f"{f.get('source_url')}\n\"{f.get('quote')}\""[:900])
                    stats["rejected_by_code"] += 1
                    continue
                src = f"{f.get('source_url')}\n\"{f.get('quote')}\" ({f.get('cycle_evidence', '')})"
                if v.get("verdict") == "correct":
                    value = str(v.get("corrected_value") or "").strip() or f["value"]
                    put(sheet, df, row, col, value, f"verified (research + verification agents, web search) | "
                                                    f"{v.get('reason', '')}\n{src}"[:900],
                        v.get("source_url") or f.get("source_url"))
                    stats["verified"] += 1
                elif v.get("verdict") == "incorrect" and (fix := str(v.get("corrected_value") or "").strip()) \
                        and not CTX.cycle_violation(f"{fix} {v.get('reason', '')}", "deadline" in col.casefold()):
                    put(sheet, df, row, col, fix, f"corrected by verification agent (research value {f['value']!r} "
                                                  f"was wrong): {v.get('reason')}\n{v.get('source_url')}"[:900], v.get("source_url"))
                    stats["verifier_corrected"] = stats.get("verifier_corrected", 0) + 1
                elif v.get("verdict") == "incorrect":
                    rejects.append({**f, "rejected": f"verifier: {v.get('reason')}"})
                    put(sheet, df, row, col, NOT_FOUND, f"candidate {f['value']!r} rejected by verifier: "
                                                        f"{v.get('reason')}\n{src}"[:900])
                    stats["rejected_by_verifier"] += 1
                else:
                    put(sheet, df, row, col, f"UNVERIFIED: {f['value']}", f"NOT VERIFIED - review | "
                        f"{v.get('reason') or 'verifier could not re-confirm'}\n{src}"[:900], f.get("source_url"))
                    stats["unverified"] += 1
    write_back(str(SRC), str(DEST), frames, changed)
    (HERE / "merge_report.json").write_text(json.dumps({"stats": stats, "rejected": rejects}, indent=1))
    print(f"-> {DEST.name}: {stats}")


if __name__ == "__main__":
    main()
