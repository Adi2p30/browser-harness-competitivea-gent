"""Claude (Anthropic Messages API) client: the fallback model when RCAC is unavailable or finds nothing."""
import json
import logging
import os
import threading
import time
from pathlib import Path

MODEL = "claude-opus-5-5"
EFFORT = "high"  # Opus 5.5 defaults to medium; extraction accuracy matters more than cost here
LLM_LOG: Path | None = None  # when set, every prompt/reply pair is appended here as JSONL
_LOCK = threading.Lock()
_client = None
log = logging.getLogger(__name__)


def _load_key() -> None:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    for env in (Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"):
        if env.is_file():
            for line in env.read_text().splitlines():
                k, _, v = line.partition("=")
                if k.strip() == "ANTHROPIC_API_KEY" and v.strip():
                    os.environ["ANTHROPIC_API_KEY"] = v.strip().strip("\"'")
                    return


def available() -> bool:
    _load_key()
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def _get_client():
    global _client
    with _LOCK:
        if _client is None:
            import anthropic
            _load_key()
            _client = anthropic.Anthropic(max_retries=6, timeout=300.0)
        return _client


def call_claude(prompt: str) -> str:
    import anthropic
    started = time.time()
    try:
        response = _get_client().messages.create(
            model=MODEL, max_tokens=16000, output_config={"effort": EFFORT},
            messages=[{"role": "user", "content": prompt}])
    except anthropic.AuthenticationError:
        raise RuntimeError("Claude rejected the API key") from None
    except anthropic.APIStatusError as exc:
        raise RuntimeError(f"Claude API error {exc.status_code}: {exc.message}") from None
    except anthropic.APIConnectionError as exc:
        raise RuntimeError(f"Claude API unreachable: {exc}") from None
    if response.stop_reason == "refusal":
        log.warning("Claude declined the request (%s)", response.stop_details)
        text = ""
    else:
        text = "".join(b.text for b in response.content if b.type == "text")
    seconds = time.time() - started
    usage = response.usage.to_dict() if hasattr(response.usage, "to_dict") else None
    log.info("Claude reply: %d chars in %.1fs (usage %s)", len(text), seconds, usage)
    if LLM_LOG:
        with _LOCK, LLM_LOG.open("a") as f:
            f.write(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "model": MODEL, "seconds": round(seconds, 1),
                                "usage": usage, "prompt": prompt, "reply": text}) + "\n")
    return text  # empty on refusal; the caller treats it as an unparseable reply
