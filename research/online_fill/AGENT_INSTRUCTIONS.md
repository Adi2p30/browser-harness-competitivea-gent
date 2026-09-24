# Research agent instructions (Online sheets, 2026-2027)

You fill one batch file `research/online_fill/batches/batch_NN.json`. Each job is one university program page
(`start_urls`); a job may cover several workbook rows (same page, e.g. two programs listed together) -- answer
every row. Jobs from the same university share tuition/admissions pages: search those once and reuse.

Read first (they are the rules):
- `agent-workspace/domain-skills/competitive-analysis/cycle-2026-2027.md` -- ONLY the 2026-2027 academic year
  (Fall 2026, Spring 2027, Summer 2027). Anything tied to another year/term is NOT an answer.
- `agent-workspace/domain-skills/competitive-analysis/field-guide.md` -- what each column means.
- `agent-workspace/domain-skills/competitive-analysis/site-patterns.md` -- where schools keep each fact.

## Tools
Direct page fetching and curl are blocked by the network policy. Use **WebSearch** only, with
`allowed_domains` set to the school's own domain(s) (e.g. `["purdue.edu"]`) so answers come from the school's
site. Ranking columns may also use the ranking publisher's domain (usnews.com, best-masters.com, topuniversities.com).
Group questions: ~8-12 searches per program, e.g.
1. "<program> tuition per credit 2026-2027" (in-state / out-of-state / international, totals)
2. "<program> application deadlines Fall 2026 Spring 2027"
3. "<program> class profile average GMAT GRE GPA work experience age women international"
4. "<program> credit hours duration months online format residency"
5. "<program> experiential learning capstone", "<school> student organizations affinity clubs", "<school> career coaching online students"
6. "<school> graduate international three-year bachelor's degree India"
7. "<program> scholarship", "<program> enrollment deposit"
8. "<program> ranking U.S. News 2026", "<program> employment report salary placement"
Stop searching a field once found or after two focused tries.

## Output
Append to `research/online_fill/findings/batch_NN.jsonl` ONE JSON object per line, for EVERY field of EVERY row
in the batch (every name in that row's `fields` list, spelled exactly), write with a Bash heredoc / python:

{"sheet": "...", "row": 7, "field": "Credit Hours", "value": "36", "status": "found",
 "source_url": "https://...", "quote": "<the sentence/snippet stating it, verbatim as the search result gave it>",
 "cycle_evidence": "2026-2027 | Fall 2026 | no year stated"}

- `status`: "found" or "not_found". For not_found set value "" and say in `quote` what you searched.
- Only values the school's page states. Never compute (no per-credit x credits), never estimate, never carry an
  older year's number forward. If the only number is for 2025-2026 or 2027-2028 -> not_found.
- `value` digits must appear in `quote`. Keep units: "$1,250", "36", "41%", "Yes", "Fall 2026: Jun 1, 2026; ...".
- For link columns (names containing "Link"), value = the URL of the page proving the paired Yes/No field.
- Flat online rate for all students -> the same value in all three residency columns only if the page says so.
When the whole batch is written, reply with one line: "batch NN: <found>/<total> fields found".
