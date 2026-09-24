"""One-off: turn the 2025-26 workbook's Website Link column into the hardcoded dict in colleges.py."""
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from openpyxl import load_workbook

SRC = "/Users/aditya_pachpande/Documents/GitHub/Aditya Pachpande Daniels-School-of-Business-Marketing-Data-Science-Analytics-Internship/10_competitive_analysis_ai_agent/Competitive Analysis Research 2025-2026.xlsx"
TRACKING = re.compile(r"^(utm_|gclid|gclsrc|gad|uadgroup|uadcampaign|fbclid|msclkid|_ga|mc_|cid$|campaignid|device$|vendorid|gbraid|wbraid)", re.I)

def clean(url):
    u = urlparse(url.strip())
    q = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if not TRACKING.match(k)]
    return urlunparse(u._replace(query=urlencode(q), fragment=""))

def norm(s): return " ".join(str(s).split()).casefold()

out = {}
wb = load_workbook(SRC, read_only=True)
for ws in wb:
    rows = list(ws.iter_rows(values_only=True))
    if not rows or not rows[0]: continue
    di = next((i for i, h in enumerate(rows[0][:6]) if h and "website link" in str(h).casefold()), None)
    if di is None: continue
    for r in rows[1:]:
        if not r[0] or not r[di] or not str(r[di]).startswith("http"): continue
        url = clean(str(r[di]))
        prog = norm(r[2]) if r[2] else ""
        out.setdefault((ws.title, norm(r[0]), prog), []).append(url)
        out.setdefault((ws.title, norm(r[0]), ""), [])
        if url not in out[(ws.title, norm(r[0]), "")]: out[(ws.title, norm(r[0]), "")].append(url)

lines = ['"""Hardcoded starting links per (sheet, university, program), seeded from the 2025-2026 workbook.',
         '',
         'Tracking parameters (utm_*, gclid, ...) were stripped. Keys are lower-cased; an empty program means',
         '"any program of that university on that sheet". Add or fix links here; the agent starts from them',
         'and follows same-site links.',
         '"""', '', 'COLLEGE_LINKS: dict[tuple[str, str, str], list[str]] = {']
for (sheet, univ, prog), urls in sorted(out.items()):
    lines.append(f'    ({sheet!r}, {univ!r}, {prog!r}): {urls!r},')
lines += ['}', '', '',
'def _norm(s) -> str:',
'    return " ".join(str(s).split()).casefold()', '', '',
'def links_for(sheet: str, college: str, program: str = "") -> list[str]:',
'    """Exact (sheet, college, program) match first, then any link for the college on that sheet."""',
'    for prog in (_norm(program), ""):',
'        urls = COLLEGE_LINKS.get((sheet, _norm(college), prog))',
'        if urls:',
'            return urls',
'    return []', '']
open("/Users/aditya_pachpande/Documents/GitHub/ice-sheet-modelling/browser-harness-competitivea-gent/agent-workspace/competitive_analysis/colleges.py", "w").write("\n".join(lines))
print(len(out), "keys")
