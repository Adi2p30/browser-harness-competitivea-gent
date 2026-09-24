"""RCAC GenAI Studio client (OpenAI-compatible chat completions)."""
import json
import logging
import os
import re
import threading
import time
from pathlib import Path

import requests

API_URL = "https://genai.rcac.purdue.edu/api/chat/completions"
MODEL = "gpt-oss:120b"
BACKOFF_BASE, BACKOFF_MAX, BACKOFF_RETRIES = 2, 60, 6
REQUEST_DEADLINE = 240  # seconds for the whole request; requests' own timeout only limits idle gaps, and the server can stall for hours
LLM_LOG: Path | None = None  # when set, every prompt/reply pair is appended here as JSONL
log = logging.getLogger(__name__)


def _api_key() -> str:
    if not os.environ.get("RCAC_API_KEY"):
        for env in (Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"):
            if env.is_file():
                for line in env.read_text().splitlines():
                    k, _, v = line.partition("=")
                    if k.strip() == "RCAC_API_KEY" and v.strip():
                        os.environ["RCAC_API_KEY"] = v.strip().strip("\"'")
    try:
        return os.environ["RCAC_API_KEY"]
    except KeyError:
        raise RuntimeError("Set RCAC_API_KEY in the environment or in .env") from None


def available() -> bool:
    try:
        return bool(_api_key())
    except RuntimeError:
        return False


LLM_LOG_LOCK = threading.Lock()  # concurrent colleges share one llm.jsonl


def _record(prompt: str, reply: str | None, seconds: float, attempts: int, usage: dict | None) -> None:
    if LLM_LOG:
        with LLM_LOG_LOCK, LLM_LOG.open("a") as f:
            f.write(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "seconds": round(seconds, 1),
                                "attempts": attempts, "usage": usage, "prompt": prompt, "reply": reply}) + "\n")


def _post(headers: dict, payload: dict) -> requests.Response:
    """requests.post with a hard overall deadline."""
    box: dict = {}

    def run() -> None:
        try:
            box["resp"] = requests.post(API_URL, headers=headers, json=payload, timeout=REQUEST_DEADLINE)
        except Exception as exc:
            box["exc"] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(REQUEST_DEADLINE)
    if "resp" in box:
        return box["resp"]
    raise box.get("exc") or requests.Timeout(f"no reply within {REQUEST_DEADLINE}s")


def call_rcac(prompt: str) -> str:
    headers = {"Authorization": f"Bearer {_api_key()}", "Content-Type": "application/json"}
    payload = {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2}
    delay = BACKOFF_BASE
    started = time.time()
    for attempt in range(1, BACKOFF_RETRIES + 1):
        log.debug("RCAC request: attempt %d, model %s, prompt %d chars", attempt, MODEL, len(prompt))
        try:
            resp = _post(headers, payload)
            if resp.status_code == 200:
                body = resp.json()
                # gpt-oss sometimes returns content: null, so treat it as retryable
                content = body["choices"][0]["message"]["content"]
                if content and content.strip():
                    seconds = time.time() - started
                    log.info("RCAC reply: %d chars in %.1fs (attempt %d, usage %s)", len(content), seconds,
                             attempt, body.get("usage"))
                    _record(prompt, content, seconds, attempt, body.get("usage"))
                    return content
                log.warning("Empty/null content on attempt %d; retrying", attempt)
            elif resp.status_code in (401, 403):
                _record(prompt, None, time.time() - started, attempt, None)
                raise RuntimeError(f"RCAC rejected the API key (HTTP {resp.status_code})")
            else:
                log.warning("HTTP %s on attempt %d: %s", resp.status_code, attempt, resp.text[:200])
        except requests.RequestException as exc:
            log.warning("Request error on attempt %d: %s", attempt, exc)
        if attempt < BACKOFF_RETRIES:
            log.info("RCAC retry in %ds", delay)
            time.sleep(delay)
            delay = min(delay * 2, BACKOFF_MAX)
    _record(prompt, None, time.time() - started, BACKOFF_RETRIES, None)
    raise RuntimeError("RCAC API failed after retries")


def parse_json(text: str) -> dict:
    """First JSON object in an LLM reply; tolerates code fences and surrounding prose."""
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    if start < 0:
        raise ValueError(f"no JSON object in reply: {text[:200]!r}")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    return obj
