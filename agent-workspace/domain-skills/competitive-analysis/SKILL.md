# Competitive analysis: filling the Online program sheets

Task: for every row of every `Online ...` sheet in
`EDIT Competitive Analysis Research 2026-2027.xlsx`, open the program's `Website Link`
in the browser harness, walk the site, and fill every column to the right of `Website Link`
with the value **for the 2026-2027 academic year only**.

The files in this folder are read by `agent-workspace/competitive_analysis` at run time.
Edit them to change what the agent looks for; no code change is needed.

| File | Used for |
|---|---|
| `cycle-2026-2027.md` | The cycle rules. Injected into every extraction and verification prompt. |
| `field-guide.md` | Per-column definitions: what counts, units, where it lives, link keywords. The section for each still-missing field is injected into the extraction prompt. `Keywords:` lines steer which links the crawler opens first. |
| `verification.md` | The checklist the second (verification) pass of the same model applies to every value. |
| `site-patterns.md` | Where university sites usually keep each kind of fact. Injected into extraction prompts. |

## Run

```bash
# 1. a browser the harness can drive (your Chrome with remote debugging, or headless Chromium):
chromium --headless=new --remote-debugging-port=9222 --user-data-dir=/tmp/bh-chrome &
export BU_CDP_URL=http://127.0.0.1:9222
./browser-harness --doctor

# 2. all Online sheets, pages rendered in the real browser, RCAC first then Claude Opus 5.5
cd agent-workspace
uv run --with openpyxl --with pandas --with requests --with beautifulsoup4 --with anthropic \
  python -m competitive_analysis "../EDIT Competitive Analysis Research 2026-2027.xlsx" --online --fetch browser
```

Needs `RCAC_API_KEY` and/or `ANTHROPIC_API_KEY` (env or `.env`); a model without a key is skipped, and with neither
the run stops before touching the workbook. Output: `..._filled.xlsx` plus `..._logs/` (run.log, llm.jsonl, pages/,
report.json). Rerunning resumes from report.json; add `--retry-unfilled` to research placeholder cells again.
If the browser never works on the first pages, the run says so and falls back to plain HTTP.

## Model order (per college)

1. **RCAC** (`gpt-oss:120b`) crawls the site and extracts candidates.
2. Fields RCAC could not fill are handed to **Claude Opus 5.5** (`claude-opus-5-5`), which
   re-reads the pages already fetched and keeps crawling for the rest.
   If RCAC is down or has no key, Claude does the whole college.
3. Every value is **verified by the same model that extracted it** (RCAC values by RCAC, Claude values by Claude)
   against the page text around its quote. Rejected values are dropped and the next candidate is tried.

## Hard rules (enforced in code, not just in prompts)

- The quote must be on the page verbatim, and every digit of the value must be in the quote.
- A quote that names any year other than 2026/2027, a range such as `2025-2026`, `Fall 2027`
  or `Spring 2026` is rejected, whatever the model said.
- Different program / degree level (undergraduate, certificate, on-campus-only when the sheet is online) is rejected.
- Every cell ends up non-blank: verified value, or a clearly marked `UNVERIFIED: ...` / `Not found (2026-27)` /
  `Not published by school`, each with a cell comment giving the source URL and quote or the pages checked.
