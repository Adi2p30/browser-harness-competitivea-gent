#!/usr/bin/env bash
# Pull each retry session's findings/verify files from its claude/retry-batch-NN branch; print which are done.
cd "$(git rev-parse --show-toplevel)"
for n in $(seq -w 1 21); do
  b="claude/retry-batch-$n"
  git fetch -q origin "$b" 2>/dev/null || { echo "$n: no branch yet"; continue; }
  for d in findings verify; do
    f="research/online_fill/retry/$d/batch_$n.jsonl"
    git show "origin/$b:$f" > "$f.tmp" 2>/dev/null && mv "$f.tmp" "$f" || rm -f "$f.tmp"
  done
  v="research/online_fill/retry/verify/batch_$n.jsonl"
  echo "$n: $(grep -c '"found"' research/online_fill/retry/findings/batch_$n.jsonl) found, $( [ -f $v ] && wc -l < $v || echo 0) verified"
done
