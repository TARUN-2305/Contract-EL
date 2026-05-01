"""
Groq API client with round-robin key rotation.
Loads KEY1–KEY4 from .env and rotates on rate-limit (429).
"""
import os
import time
import threading
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Load all keys
_KEYS = [v for k, v in sorted(os.environ.items()) if k.startswith("KEY") and v.startswith("gsk_")]
_key_index = 0
_lock = threading.Lock()


def _next_key() -> str:
    global _key_index
    with _lock:
        key = _KEYS[_key_index % len(_KEYS)]
        _key_index += 1
        return key


def groq_chat(
    messages: list,
    model: str = "llama-3.3-70b-versatile",
    max_tokens: int = 4096,
    temperature: float = 0.1,
    retries: int = len(_KEYS),
) -> Optional[str]:
    """
    Call Groq chat completion with automatic key rotation on 429.

    Args:
        messages: list of {"role": "system"|"user"|"assistant", "content": str}
        model: Groq model ID. Use:
               "llama-3.3-70b-versatile"  — extraction, compliance reasoning
               "llama-3.1-8b-instant"     — narration, audience-aware reports
        max_tokens: response length cap
        temperature: 0.0–0.1 for deterministic extraction, 0.3+ for narration
        retries: number of key rotations to attempt before raising

    Returns:
        str response content, or None on total failure
    """
    if not _KEYS:
        raise RuntimeError(
            "No Groq API keys found. Add KEY1=gsk_... KEY2=gsk_... to .env"
        )

    try:
        from groq import Groq
    except ImportError:
        raise RuntimeError("groq package not installed. Run: pip install groq")

    last_exc = None
    for attempt in range(retries):
        key = _next_key()
        try:
            client = Groq(api_key=key)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            last_exc = e
            err_str = str(e).lower()
            if "429" in err_str or "rate" in err_str:
                print(f"[GroqClient] Rate limit on key #{attempt+1}, rotating... ({e})")
                time.sleep(0.5)
                continue
            elif "401" in err_str or "invalid" in err_str:
                print(f"[GroqClient] Invalid key #{attempt+1}, rotating...")
                continue
            else:
                # Non-retryable error
                raise

    print(f"[GroqClient] All {retries} key attempts exhausted. Last error: {last_exc}")
    return None


def groq_json_extract(
    system_prompt: str,
    user_content: str,
    model: str = "llama-3.3-70b-versatile",
) -> Optional[str]:
    """
    Convenience wrapper for JSON extraction tasks.
    Sets temperature=0.0 for maximum determinism.
    """
    return groq_chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        model=model,
        temperature=0.0,
        max_tokens=4096,
    )


def groq_narrate(
    system_prompt: str,
    user_content: str,
    model: str = "llama-3.1-8b-instant",
) -> Optional[str]:
    """
    Convenience wrapper for narrative/explanation tasks.
    Uses faster 8b model and slightly higher temperature for readable prose.
    """
    return groq_chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        model=model,
        temperature=0.3,
        max_tokens=2048,
    )


def get_groq_client():
    """Return a Groq client using the next available key, or None if no keys."""
    if not _KEYS:
        return None
    try:
        from groq import Groq
        return Groq(api_key=_next_key())
    except ImportError:
        return None


# ── Quick health check ──────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"[GroqClient] Loaded {len(_KEYS)} API key(s)")
    result = groq_chat(
        messages=[{"role": "user", "content": "Reply with exactly: GROQ_OK"}],
        model="llama-3.1-8b-instant",
        max_tokens=10,
    )
    print(f"[GroqClient] Health check: {result}")
