# Retry research instructions (Online sheets, 2026-2027, second search pass)

You fill one retry batch `research/online_fill/retry/batches/batch_NN.json`. It lists ONLY the cells the first
pass could not fill; `first_pass` shows, per field, what was tried / why it failed. Do not repeat the same
searches: search differently (other wording, other pages of the school, the publishers below).

Rules are the same as `research/online_fill/AGENT_INSTRUCTIONS.md` (read it) plus
`agent-workspace/domain-skills/competitive-analysis/{cycle-2026-2027,field-guide,site-patterns}.md`:
2026-2027 cycle only, values stated on the page, never computed or estimated, digits must be in the quote.

## Where to look, by field
- **Ranking (U.S. News)** -> go to U.S. News itself: WebSearch with `allowed_domains=["usnews.com"]`
  (e.g. "<school> online MBA ranking", "<school> online master's business ranking"). Use the 2026 edition
  (Best Online Programs 2026 / Best Graduate Schools 2026) or a page with no edition year. Value like
  "#12 (2026 Best Online MBA Programs)". If the program is "Unranked" / "Rank Not Published" say so as the value.
- **Ranking (Best-Masters.com)** -> go to Best Masters: `allowed_domains=["best-masters.com"]`
  (e.g. "<school> online MBA best masters ranking"). Value like "#8 (Best Online MBA 2026)".
- **Ranking (QS)** -> go to QS: `allowed_domains=["topuniversities.com"]` (QS Online MBA / Business Masters
  rankings 2026). Value like "#15 (QS Online MBA Rankings 2026)".
- **Job Placement %, Average Post-Grad Salary, Average Post-Grad Bonus** -> first the school's own site
  (employment report / outcomes page for this program). If the school does not state it, go to U.S. News
  (`usnews.com`) and then Best Masters (`best-masters.com`) program profiles.
- Every other field -> the school's own domain(s) only (try sibling domains: the business school subdomain,
  registrar / bursar / graduate school / admissions, the program's PDF viewbook or FAQ).
- If a ranking publisher does not rank this program, give `not_found` with the searches in `quote`.

## Links are required
`source_url` must be the exact page the value came from (U.S. News / Best Masters / school page). It is written
into the workbook as the cell's hyperlink, so never leave it blank on a "found" line.

## Output
Append to `research/online_fill/retry/findings/batch_NN.jsonl` one JSON line per field listed in each row's
`fields` + `link_columns` (spelled exactly), same schema as the first pass plus `"source": "school|usnews|best-masters|qs"`:

{"sheet": "...", "row": 7, "field": "Ranking (U.S. News)", "value": "#12 (2026 Best Online MBA Programs)",
 "status": "found", "source": "usnews", "source_url": "https://www.usnews.com/...",
 "quote": "<verbatim snippet>", "cycle_evidence": "2026 edition | no year stated"}

Reply with one line: "retry NN: <found>/<total> fields found".
