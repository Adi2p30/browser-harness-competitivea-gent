"""Fetch a page and return its readable text, same-site links and freshness hints."""
import hashlib
import logging
import os
import threading
import subprocess
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)
PAGE_DIR: Path | None = None  # when set, the full text of every fetched page is saved here
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; competitive-analysis-agent)"}
MIN_READABLE = 200  # fewer characters than this usually means a JavaScript-rendered page
USE_BROWSER = os.environ.get("BH_FETCH") == "1"  # retry pages requests can't read through browser-harness
BROWSER_GIVE_UP = 5  # browser-first falls back to plain HTTP if the browser never worked on this many pages
BROWSER_FIRST = False  # --fetch browser: render every page in the real browser, plain HTTP only as fallback
TAB_MARKER = "\U0001f434 "
STATS = {"requests": 0, "browser": 0, "browser_rescued": 0, "browser_failed": 0}
SKIP_EXT = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".zip", ".doc", ".docx",
            ".xls", ".xlsx", ".ppt", ".pptx", ".mp4", ".mp3")


class Page(NamedTuple):
    text: str
    links: list[tuple[str, str]]  # (anchor_text, absolute_url), same site only
    last_modified: str            # HTTP Last-Modified header, "" if absent


def _site(url: str) -> str:
    return ".".join(urlparse(url).netloc.lower().split(".")[-2:])


def _via_requests(url: str, timeout: int) -> tuple[str, str, str] | None:
    """(html, final_url, last_modified), or None if it can't be fetched or isn't HTML."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
    except requests.RequestException as exc:
        log.warning("FETCH FAILED %s: %s", url, exc)
        return None
    log.debug("  -> HTTP %s, final url %s, content-type %r, %d bytes, Last-Modified %r",
              resp.status_code, resp.url, resp.headers.get("content-type"), len(resp.content),
              resp.headers.get("last-modified"))
    if resp.status_code != 200 or "html" not in resp.headers.get("content-type", ""):
        log.warning("FETCH SKIPPED %s: HTTP %s, %s", url, resp.status_code, resp.headers.get("content-type"))
        return None
    return resp.text, resp.url, resp.headers.get("last-modified", "")


_tab = None
_BROWSER_LOCK = threading.Lock()  # one real Chrome tab is shared; serialize goto/read so concurrent colleges don't collide


def _harness():
    """browser-harness helpers, wired to the same daemon the ./browser-harness launcher uses."""
    root = Path(__file__).resolve().parents[2]
    dev_id = subprocess.run(["cksum"], input=str(root), text=True, capture_output=True).stdout.split()[0]
    os.environ.setdefault("BH_HOME", str(root / ".browser-harness-dev"))
    os.environ.setdefault("BH_RUNTIME_DIR", f"/tmp/bh-dev-{dev_id}/runtime")
    os.environ.setdefault("BH_RUNTIME_DIR_SHARED", "1")
    os.environ.setdefault("BH_TMP_DIR", str(root / ".browser-harness-dev" / "tmp"))
    os.environ.setdefault("BH_TMP_DIR_SHARED", "1")
    from browser_harness import helpers
    from browser_harness.admin import ensure_daemon
    ensure_daemon()
    return helpers


def check_link(url: str) -> str:
    """Open the URL in a real browser: "ok (HTTP 200)" for a page that loads, else "FAIL: <why>"."""
    global _tab
    try:
        with _BROWSER_LOCK:
            h = _harness()
            _tab = _tab or h.new_tab()
            h.switch_tab(_tab)
            h.goto_url(url)
            h.wait_for_load(20)
            h.wait(1)
            status, final, size = h.js("[performance.getEntriesByType('navigation')[0]?.responseStatus || 0, location.href,"
                                       " (document.body?.innerText || '').length]")
    except Exception as exc:
        return f"FAIL: {exc}"
    if not final.startswith(("http://", "https://")):
        return "FAIL: browser could not load the page"
    return f"ok (HTTP {status})" if status < 400 and size else f"FAIL: HTTP {status}, {size} chars of text"


def _via_browser(url: str) -> tuple[str, str, str] | None:
    """Render the page in a real browser through browser-harness (needs BU_CDP_URL/BU_CDP_WS or a debuggable Chrome)."""
    global _tab
    try:
        with _BROWSER_LOCK:
            h = _harness()
            goto_url, js, wait, wait_for_load = h.goto_url, h.js, h.wait, h.wait_for_load
            _tab = _tab or h.new_tab()
            h.switch_tab(_tab)
            goto_url(url)
            wait_for_load(20)
            for _ in range(10):  # JS-rendered and challenge pages fill in after the load event
                try:
                    if len(js("document.body.innerText")) >= MIN_READABLE:
                        break
                except Exception:  # mid-navigation, no body yet
                    pass
                wait(1)
            html, final = js("[document.documentElement.outerHTML, location.href]")
    except Exception as exc:
        log.warning("BROWSER FETCH FAILED %s: %s", url, exc)
        return None
    if not final.startswith(("http://", "https://")):  # chrome-error:// etc.
        log.warning("BROWSER FETCH FAILED %s: browser error page %s", url, final)
        return None
    return html.replace(TAB_MARKER, ""), final, ""  # the harness prefixes tab titles with a marker


def _parse(html: str, url: str, last_modified: str) -> Page:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    links, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = urldefrag(urljoin(url, a["href"]))[0]
        skip = ("not http(s)" if urlparse(href).scheme not in ("http", "https") else
                "duplicate" if href in seen else
                "file type skipped" if href.lower().endswith(SKIP_EXT) else
                "other site" if _site(href) != _site(url) else None)
        if skip:
            log.debug("  link dropped (%s): %s", skip, href)
            continue
        seen.add(href)
        links.append((" ".join(a.get_text().split())[:80], href))
    return Page(" ".join(soup.get_text(" ").split()), links, last_modified)


def fetch(url: str, timeout: int = 20) -> Page | None:
    """An HTML page, or None if it can't be fetched or isn't HTML. With BROWSER_FIRST every page is rendered in the
    real browser via browser-harness (plain HTTP if that fails); with BH_FETCH=1, pages plain HTTP cannot fetch or
    that hold almost no text are retried in the browser."""
    global BROWSER_FIRST
    log.info("FETCH %s", url)
    got = page = None
    if BROWSER_FIRST:
        got = _via_browser(url)
        page = _parse(*got) if got else None
        if page and len(page.text) >= MIN_READABLE:
            STATS["browser"] += 1
        else:
            STATS["browser_failed"] += 1
            if STATS["browser"] == 0 and STATS["browser_failed"] >= BROWSER_GIVE_UP:
                BROWSER_FIRST = False
                log.error("Browser-harness failed on the first %d pages and never worked; continuing with plain HTTP. "
                          "Check ./browser-harness --doctor", BROWSER_GIVE_UP)
            log.info("  browser gave %s; falling back to plain HTTP", "nothing" if page is None else f"{len(page.text)} chars")
            got = page = None
    if page is None:
        got = _via_requests(url, timeout)
        page = _parse(*got) if got else None
        if USE_BROWSER and not BROWSER_FIRST and (page is None or len(page.text) < MIN_READABLE):
            log.info("  retrying in the browser (%s)", "requests failed" if page is None else f"only {len(page.text)} chars")
            rendered = _via_browser(url)
            rescued = _parse(*rendered) if rendered else None
            if rescued and len(rescued.text) >= MIN_READABLE:
                STATS["browser_rescued"] += 1
                log.info("  BROWSER RESCUED %s: %d chars", url, len(rescued.text))
                page, got = rescued, rendered
            else:
                STATS["browser_failed"] += 1
        elif got:
            STATS["requests"] += 1
    if page is None:
        return None
    text = page.text
    digest = hashlib.sha1(text.encode()).hexdigest()[:10]
    log.debug("  text: %d chars (sha1 %s); %d same-site links kept", len(text), digest, len(page.links))
    for anchor, href in page.links:
        log.debug("  link: %s | %s", anchor or "(no text)", href)
    if PAGE_DIR:
        PAGE_DIR.mkdir(parents=True, exist_ok=True)
        saved = PAGE_DIR / f"{hashlib.sha1(url.encode()).hexdigest()[:8]}_{digest}.txt"
        saved.write_text(f"URL: {got[1]}\nLast-Modified: {page.last_modified}\n\n{text}\n")
        log.debug("  saved page text -> %s", saved)
    return page
