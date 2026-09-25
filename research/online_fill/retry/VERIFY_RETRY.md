# Verification of the retry pass

Follow `research/online_fill/VERIFY_INSTRUCTIONS.md`, with these paths:
- input: `research/online_fill/retry/findings/batch_NN.jsonl` (rows in `research/online_fill/retry/batches/batch_NN.json`)
- output: `research/online_fill/retry/verify/batch_NN.jsonl` (same line schema)

Re-check on the same kind of source the finding used (`source` field): school -> the school's domain;
usnews -> `usnews.com`; best-masters -> `best-masters.com`; qs -> `topuniversities.com`.
Rankings: the rank must be for THIS program's category (e.g. online MBA, not full-time MBA; business analytics,
not the whole school) and a 2026/2027 edition or undated current page. Placement / salary / bonus from a
publisher must be for this online program. `source_url` in your line must be the page you confirmed it on.
