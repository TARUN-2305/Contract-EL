"""
LLM Client with fallback chain: Groq → Ollama gemma3:1b → Ollama phi3:mini
Large timeouts for CPU-based Ollama inference.
"""
import os
import time
import threading
import json
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class LLMClient:
    """
    Unified LLM client with automatic fallback:
    1. Groq API (fast, cloud) - rotates between multiple keys
    2. Ollama gemma3:1b (local CPU) 
    3. Ollama phi3:mini (local CPU, smaller fallback)
    """

    def __init__(self):
        from config import settings
        self.settings = settings
        self._groq_keys = settings.get_groq_keys()
        self._key_index = 0
        self._lock = threading.Lock()

    def _next_groq_key(self) -> Optional[str]:
        if not self._groq_keys:
            return None
        with self._lock:
            key = self._groq_keys[self._key_index % len(self._groq_keys)]
            self._key_index += 1
            return key

    def _groq_call(self, messages: list, model: str, max_tokens: int, temperature: float) -> Optional[str]:
        """Try Groq API with key rotation."""
        if not self._groq_keys:
            return None
        try:
            from groq import Groq
        except ImportError:
            return None

        for attempt in range(len(self._groq_keys)):
            key = self._next_groq_key()
            try:
                client = Groq(api_key=key)
                resp = client.chat.completions.create(
                    model=model, messages=messages,
                    max_tokens=max_tokens, temperature=temperature
                )
                return resp.choices[0].message.content
            except Exception as e:
                err = str(e).lower()
                if "429" in err or "rate" in err:
                    print(f"[LLM] Groq rate limit key #{attempt+1}, rotating...")
                    time.sleep(1)
                    continue
                elif "401" in err or "invalid" in err:
                    print(f"[LLM] Groq invalid key #{attempt+1}, rotating...")
                    continue
                else:
                    print(f"[LLM] Groq error: {e}")
                    return None
        return None

    def _ollama_call(self, messages: list, model: str) -> Optional[str]:
        """Try Ollama local inference with large timeout."""
        try:
            import httpx
            url = f"{self.settings.ollama_url}/api/chat"
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 4096}
            }
            resp = httpx.post(url, json=payload, timeout=self.settings.ollama_timeout)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("message", {}).get("content")
            else:
                print(f"[LLM] Ollama {model} returned {resp.status_code}")
                return None
        except Exception as e:
            print(f"[LLM] Ollama {model} error: {e}")
            return None

    def embed(self, text: str) -> Optional[list[float]]:
        """Get embeddings from Ollama."""
        try:
            import httpx
            url = f"{self.settings.ollama_url}/api/embeddings"
            payload = {
                "model": self.settings.ollama_embed_model,
                "prompt": text
            }
            resp = httpx.post(url, json=payload, timeout=60)
            if resp.status_code == 200:
                return resp.json().get("embedding")
            else:
                # Try fallback to primary model if dedicated embed model fails
                payload["model"] = self.settings.ollama_primary_model
                resp = httpx.post(url, json=payload, timeout=60)
                if resp.status_code == 200:
                    return resp.json().get("embedding")
                return None
        except Exception as e:
            print(f"[LLM] Embedding error: {e}")
            return None

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings for a list of strings."""
        results = []
        for text in texts:
            emb = self.embed(text)
            if emb:
                results.append(emb)
            else:
                # Return zero vector if it fails
                results.append([0.0] * 384) 
        return results

    def chat(
        self,
        messages: list,
        model: str = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> Optional[str]:
        """
        Chat with fallback chain.
        1. Try Groq with specified model
        2. Try Ollama gemma3:1b
        3. Try Ollama phi3:mini
        """
        if model is None:
            model = self.settings.llm_model_extraction

        # Step 1: Groq
        result = self._groq_call(messages, model, max_tokens, temperature)
        if result:
            return result
        print("[LLM] Groq failed, falling back to Ollama...")

        # Step 2: Ollama primary
        result = self._ollama_call(messages, self.settings.ollama_primary_model)
        if result:
            print(f"[LLM] Using Ollama {self.settings.ollama_primary_model}")
            return result
        print(f"[LLM] Ollama {self.settings.ollama_primary_model} failed, trying fallback...")

        # Step 3: Ollama fallback
        result = self._ollama_call(messages, self.settings.ollama_fallback_model)
        if result:
            print(f"[LLM] Using Ollama {self.settings.ollama_fallback_model}")
            return result

        print("[LLM] All LLM options exhausted!")
        return None

    def json_extract(self, system_prompt: str, user_content: str) -> Optional[str]:
        """Extraction task - use deterministic settings."""
        return self.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            model=self.settings.llm_model_extraction,
            temperature=0.0,
            max_tokens=4096,
        )

    def narrate(self, system_prompt: str, user_content: str) -> Optional[str]:
        """Narration task - slightly more creative."""
        return self.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            model=self.settings.llm_model_narration,
            temperature=0.3,
            max_tokens=2048,
        )

    def status(self) -> dict:
        """Return LLM availability status."""
        groq_ok = len(self._groq_keys) > 0
        ollama_primary_ok = self._ollama_call(
            [{"role": "user", "content": "Reply: OK"}],
            self.settings.ollama_primary_model
        ) is not None

        return {
            "groq_keys_loaded": len(self._groq_keys),
            "groq_available": groq_ok,
            "ollama_primary": self.settings.ollama_primary_model,
            "ollama_fallback": self.settings.ollama_fallback_model,
            "ollama_url": self.settings.ollama_url,
            "fallback_chain": ["groq", self.settings.ollama_primary_model, self.settings.ollama_fallback_model],
        }


# Singleton
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


# Legacy compat wrappers (used by existing agents)
def groq_chat(messages, model="llama-3.3-70b-versatile", max_tokens=4096, temperature=0.1, retries=4):
    return get_llm_client().chat(messages, model=model, max_tokens=max_tokens, temperature=temperature)

def groq_json_extract(system_prompt, user_content, model="llama-3.3-70b-versatile"):
    return get_llm_client().json_extract(system_prompt, user_content)

def groq_narrate(system_prompt, user_content, model="llama-3.1-8b-instant"):
    return get_llm_client().narrate(system_prompt, user_content)

def get_groq_client():
    """Legacy compat - returns LLMClient."""
    return get_llm_client()
