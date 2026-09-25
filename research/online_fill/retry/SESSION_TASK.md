# One retry batch in a fresh session (own 200-search budget)

You own batch NN (given in your prompt). Work in the repo root. Fetch/curl are blocked; use WebSearch only.

1. Research: follow `research/online_fill/retry/RETRY_INSTRUCTIONS.md` for
   `research/online_fill/retry/batches/batch_NN.json`. The existing `retry/findings/batch_NN.jsonl` is from a
   run that ran out of searches: keep its `"status": "found"` lines, drop the rest, then append fresh lines for
   every other field (lines are "last wins" per cell). Budget: at most ~140 searches for research.
2. Verify: follow `research/online_fill/retry/VERIFY_RETRY.md` for every found line, writing
   `research/online_fill/retry/verify/batch_NN.jsonl`. Keep ~50 searches for this. Verify with a fresh mind:
   search for the fact again independently; do not trust the research line.
3. Commit only those two files with message "Online fill retry: batch NN (research + verification)" and push to
   the branch you were started on. Do not touch any other file, the workbook, or merge.py.
Reply with one line: "batch NN: <found>/<total> found, <correct>/<incorrect>/<unconfirmed> verified".
