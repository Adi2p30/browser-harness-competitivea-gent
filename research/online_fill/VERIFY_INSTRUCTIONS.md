# Verification agent instructions (second pass, same model, fresh context)

You check the findings of one batch: `research/online_fill/findings/batch_NN.jsonl`
(rows/programs are described in `research/online_fill/batches/batch_NN.json`).

Read first: `agent-workspace/domain-skills/competitive-analysis/verification.md`,
`cycle-2026-2027.md` and `field-guide.md` in the same folder.

For EVERY line with `"status": "found"`:
1. Re-check it independently with **WebSearch** (fetch/curl are blocked), `allowed_domains` = the school's
   domain (or the ranking publisher for ranking columns). Search for the specific fact, not the value.
2. Apply the five checks in verification.md: present, right field, right program (this online program),
   right cycle (2026-2027 or no year stated), right format.
3. Append one line to `research/online_fill/verify/batch_NN.jsonl`:

{"sheet": "...", "row": 7, "field": "...", "verdict": "correct|incorrect|unconfirmed",
 "corrected_value": "", "reason": "<one sentence>", "source_url": "<page you confirmed it on>"}

- "correct": you found the same value for the same program and cycle. If only the format is off, give
  `corrected_value` (its digits must be in the original quote or your source).
- "incorrect": wrong program, wrong year, wrong field, or a different value is stated for 2026-2027
  (put that value in `corrected_value` only if you are certain and it is for 2026-2027).
- "unconfirmed": you could not find it again.
Group your searches by topic (tuition, deadlines, class profile...) to keep it fast. Do not edit other files.
Reply with one line: "verify NN: <correct>/<incorrect>/<unconfirmed>".
