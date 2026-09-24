"""Build research batches for the Online sheets. Rows that share a start page are merged into one job."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent-workspace"))
from competitive_analysis.__main__ import SCHOOL_COLUMN, is_note_row  # noqa: E402
from competitive_analysis.colleges import links_for, no_online_program  # noqa: E402
from competitive_analysis.excel_io import classify_columns, is_blank, load_frames, website_column  # noqa: E402

BATCH = 3
frames = load_frames(str(ROOT / "EDIT Competitive Analysis Research 2026-2027.xlsx"))
jobs: dict[str, dict] = {}
for sheet, df in frames.items():
    if not sheet.startswith("Online") or df.empty or website_column(df) is None:
        continue
    fields, link_cols, _ = classify_columns(df)
    fields = [SCHOOL_COLUMN, "Location - City", "Location - State"] + [f for f in fields if not f.startswith("Location")]
    web = df.columns[website_column(df)]
    for row in df.index:
        college = "" if is_blank(df.iloc[row, 0]) else str(df.iloc[row, 0]).strip()
        if not college or is_note_row(college) or no_online_program(sheet, college):
            continue
        program = "" if is_blank(df.iloc[row, 2]) else str(df.iloc[row, 2]).strip()
        urls = list(dict.fromkeys(([] if is_blank(df.at[row, web]) else [str(df.at[row, web]).strip()])
                                  + links_for(sheet, college, program)))
        key = urls[0] if urls else f"{sheet}|{college}"
        job = jobs.setdefault(key, {"job": key, "college": college, "start_urls": urls, "rows": []})
        job["rows"].append({"sheet": sheet, "row": row + 2, "program": program or "(not given)",
                            "fields": fields, "link_columns": link_cols})
ordered = list(jobs.values())
# Same university -> same batch (shared tuition / admissions / bursar pages are read once).
by_school: dict[str, list[dict]] = {}
for j in ordered:
    by_school.setdefault(j["college"].split(" - ")[0].split("-")[0].strip(), []).append(j)
batches, current = [], []
for group in sorted(by_school.values(), key=len, reverse=True):
    if len(group) >= BATCH:
        batches.append(group)
        continue
    if len(current) + len(group) > BATCH:
        batches.append(current)
        current = []
    current += group
if current:
    batches.append(current)
out = Path(__file__).parent / "batches"
out.mkdir(exist_ok=True)
for old in out.glob("batch_*.json"):
    old.unlink()
for i, b in enumerate(batches, 1):
    (out / f"batch_{i:02d}.json").write_text(json.dumps(b, indent=1))
print(f"{sum(len(j['rows']) for j in ordered)} rows -> {len(ordered)} jobs -> {len(batches)} batches")
for i, b in enumerate(batches, 1):
    print(f"  batch {i:02d}:", "; ".join(f"{j['college']} x{len(j['rows'])}" for j in b))
print("shared-page jobs:", [(j["college"], [r["sheet"] for r in j["rows"]]) for j in ordered if len(j["rows"]) > 1])
