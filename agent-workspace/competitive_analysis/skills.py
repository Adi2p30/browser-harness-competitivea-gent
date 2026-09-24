"""Load the agent's skill files (agent-workspace/domain-skills/competitive-analysis/*.md) into prompt text.

field-guide.md sections look like:
    ## Title
    Matches: <regex matched against the column name>
    Keywords: comma, separated, link, words
    <definition text>
"""
import re
from functools import lru_cache
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1] / "domain-skills" / "competitive-analysis"


def _read(name: str) -> str:
    path = SKILL_DIR / name
    return path.read_text(encoding="utf-8").strip() if path.is_file() else ""


@lru_cache(maxsize=None)
def _guide() -> tuple[tuple[re.Pattern, tuple[str, ...], str], ...]:
    sections = []
    for block in re.split(r"^## ", _read("field-guide.md"), flags=re.M)[1:]:
        lines = block.strip().splitlines()
        meta = {k: "" for k in ("matches", "keywords")}
        body = []
        for line in lines[1:]:
            key, sep, value = line.partition(":")
            if sep and key.strip().casefold() in meta and not body:
                meta[key.strip().casefold()] = value.strip()
            elif line.strip():
                body.append(line.strip())
        if meta["matches"]:
            keywords = tuple(k.strip().casefold() for k in meta["keywords"].split(",") if k.strip())
            sections.append((re.compile(meta["matches"], re.I), keywords, " ".join(body)))
    return tuple(sections)


def _section(field: str):
    return next((s for s in _guide() if s[0].search(field)), None)


def field_hint(field: str) -> str:
    s = _section(field)
    return s[2] if s else ""


def field_keywords(fields: list[str]) -> set[str]:
    return {k for f in fields if (s := _section(f)) for k in s[1]}


def fields_block(fields: list[str]) -> str:
    """The "fields still needed" list, each with its definition from the field guide."""
    return "\n".join(f"- {f}" + (f"\n    how to read it: {h}" if (h := field_hint(f)) else "") for f in fields)


@lru_cache(maxsize=None)
def cycle_rules() -> str:
    return _read("cycle-2026-2027.md")


@lru_cache(maxsize=None)
def site_patterns() -> str:
    return _read("site-patterns.md")


@lru_cache(maxsize=None)
def verification_rules() -> str:
    return _read("verification.md")
