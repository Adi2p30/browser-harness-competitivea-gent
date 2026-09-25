# Verification checklist (second pass, same model)

You are shown one value that was extracted from a university page, the quote it came from,
and the page text around that quote. Answer "correct" only if **every** check passes:

1. **Present**: the quote is on the page and the value is stated in it (not computed, not inferred).
2. **Right field**: the value answers exactly this column as defined in the field guide
   (per-credit vs total tuition, in-state vs out-of-state vs international, average vs median vs range,
   months vs years, application deadline vs start date vs decision date).
3. **Right program**: it is for the target program and delivery format of the sheet
   (the online master's named on the row), or a school-wide graduate value that clearly applies to it.
   Not undergraduate, not a certificate, not a different master's, not the on-campus version if its figure differs.
4. **Right cycle**: it is for the 2026-2027 academic year (Fall 2026 / Spring 2027 / Summer 2027) or
   the page names no year at all. Any other year = incorrect.
5. **Right format**: numbers keep the page's unit, `$` amounts are copied exactly, percentages keep `%`,
   Yes/No fields answer `Yes` or `No` and the answer is supported by the quote.

If the value is wrong only in format (e.g. "$1,250 per credit" should be "$1,250"), answer
"correct" and give the fixed value in `corrected_value`; the fix must still come from the quote.
If any check fails, answer "incorrect" with the failed check number.
