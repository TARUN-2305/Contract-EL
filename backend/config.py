"""
config.py — Centralised settings via Pydantic Settings.
Supports: PostgreSQL, Redis, Qdrant, Groq→Ollama LLM fallback chain.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ── Database
    database_url: str = "postgresql://postgres:contractguard@db:5432/contractguard"

    # ── Redis (Celery broker + result backend)
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    # ── Qdrant vector DB
    qdrant_url: str = "http://qdrant:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_collection: str = "contract_clauses"

    # ── LLM Fallback Chain: Groq → Ollama
    key1: Optional[str] = None
    key2: Optional[str] = None
    key3: Optional[str] = None
    key4: Optional[str] = None
    ollama_url: str = "http://ollama:11434"
    ollama_primary_model: str = "gemma4:e2b" # Updated from gemma3:1b
    ollama_fallback_model: str = "phi3:latest" # Updated from phi3:mini
    ollama_embed_model: str = "nomic-embed-text" # Standard embedding model
    ollama_timeout: int = 300

    llm_model_extraction: str = "llama-3.3-70b-versatile"
    llm_model_narration: str = "llama-3.1-8b-instant"

    # ── Weather / News
    weather_source: str = "open_meteo"
    weather_manual_data: Optional[str] = None
    gnews_api_key: Optional[str] = None
    news_override_file: Optional[str] = None

    # ── API Security
    api_key_header: Optional[str] = None
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    require_api_key: str = "false"

    data_dir: str = "/app/data"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"

    def get_groq_keys(self) -> list:
        keys = []
        for k in [self.key1, self.key2, self.key3, self.key4]:
            if k and str(k).startswith("gsk_"):
                keys.append(k)
        return keys


settings = Settings()
