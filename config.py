"""
config.py — centralised settings via Pydantic Settings.
All values readable from .env file or environment variables.
"""
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://postgres:helloPeter%402005@localhost:5432/contractguard"

    # Weather
    weather_source: str = "open_meteo"          # "open_meteo" | "manual" | "synthetic"
    weather_manual_data: Optional[str] = None    # JSON string override

    # News
    gnews_api_key: Optional[str] = None
    news_override_file: Optional[str] = None     # path to JSON override file

    # Parser
    llm_fallback_enabled: bool = True
    llm_model_extraction: str = "llama-3.3-70b-versatile"
    llm_model_narration: str = "llama-3.1-8b-instant"

    # API
    api_key_header: Optional[str] = None         # if set, all endpoints require X-API-Key header
    cors_origins: str = "http://localhost:5173,http://localhost:3000"   # React dev server

    # Frontend
    react_build_dir: str = "frontend/dist"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"

settings = Settings()
