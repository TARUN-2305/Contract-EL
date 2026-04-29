"""Quick test of Ollama LLM call without memory contention."""
import ollama
from httpx import Timeout

c = ollama.Client(timeout=Timeout(120.0))
r = c.chat(
    model="gemma4:e2b",
    messages=[{"role": "user", "content": "Return a JSON object with a greeting field. Example: {\"greeting\": \"hello\"}"}],
)
print("RESPONSE:", r["message"]["content"])
