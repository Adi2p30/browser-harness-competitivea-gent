# Program-link discovery: progress log

Goal: fill blank "Website Link" cells in `EDIT Competitive Analysis Research 2026-2027.xlsx`
(then `python -m competitive_analysis.apply_links` from agent-workspace).

## History
- 2026-09-18: 8 parallel Opus agents ("Find program links batch 1-8") hit the session rate limit (HTTP 429).
  Their partial output is in `agent-workspace/competitive_analysis/state/links_{1..8}.json`
  (entries with `note: "PENDING"` and `url: null` were NOT researched; entries with url null and another note = researched, not found).
- 2026-09-19: recovered state -> 178/254 rows done, 76 remaining. Split into `remaining_1.json`, `remaining_2.json`
  (2 agents, not 8). Each agent appends ONE JSON line per finished row to `findings/remaining_N.jsonl`
  and a text line per action to `agent_logs/agent_N.log`. Resume = rerun rows in remaining_N.json not yet in the jsonl.

## Resume recipe
    python3 research/link_discovery/status.py     # shows done/remaining per agent file
- 2026-09-19: agent 2 finished 38/38. Agent 1 was at 33/38 (MS GSCM rows 4-8 left). Note: remaining_2.jsonl has 3 extra lines (MS BAIM 27 x2, 31) written by agent 1; merge dedupes by (sheet,row), preferring the file matching the row's assignment.
- 2026-09-19 02:40: round 1 done (76 rows -> `links_final.json`); applied 247 links to the EDIT workbook via apply_links
  (backup: `EDIT Competitive Analysis Research 2026-2027_before_links.xlsx`; 9 rejected for SSL/connection errors, 6+ low-confidence not written).
  BUG FOUND: my "done" filter only treated exact note 'PENDING' as unresearched; ~37 rows had 'pending'/'Pending'/'not yet researched'
  (Accounting, BAIM, HRM, Marketing). Round 2 = `remaining_3.json`, `remaining_4.json` -> `findings/remaining_{3,4}.jsonl`, `agent_logs/agent_{3,4}.log`.
  After round 2: merge into `links_final_2.json`, rerun apply_links with all links_*.json + links_final.json + links_final_2.json (only blank cells are filled, so it is safe to rerun).
- 2026-09-19: agent 3 finished 19/19 (high 14, medium 2, low 3). Waiting on agent 4.
- 2026-09-19 02:50: round 2 done (38 rows -> `links_final_2.json`), apply_links rerun: 30 more links written.
  Workbook now has 277 link cells filled of 314 rows; 37 blank.
  Blank = 14 rejected by the reachability check (mostly SSLError/ConnectionError/ReadTimeout, likely the sites refusing scripts;
  e.g. UCI Merage, Penn State Smeal, NYU Shanghai, Baruch, Georgetown 404, IU Kelley, MSU Broad, BU COM, Villanova, Babson)
  + ~10 genuine "no such program" rows + ~15 low-confidence links deliberately not written (all listed in
  `EDIT ..._logs/apply_links.log`). Every rejected URL is still in links_final*.json and can be pasted after a manual check.
  NEXT: the actual field-filling run (`python -m competitive_analysis "<xlsx>" --cycle "2026-2027 academic year"`), not yet run on the full workbook.
